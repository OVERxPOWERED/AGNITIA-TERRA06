"""Evaluate the served forecast on the operator's own measured history (their plant, their site, their data).

For every day in the uploaded period the forecast is re-issued exactly as the live system would have issued it
(00 UTC, 48 h, archived Open-Meteo forecasts from the Previous Runs API, no actual weather as a feature),
transferred to the operator's plant through the physics ratio and calibration, and scored against what the plant
measured. The same harness functions as the Dewas evaluation produce every number:
  accuracy (metrics_table), trust check, deviation charges (DSM), value of forecast and impact.

Honesty notes carried into the result:
  - the ML models were never trained on this data, so every day is out-of-sample for them;
  - calibration: one factor per source, the recency-weighted ratio of measured output to the served forecast on
    the first 80% of the period ("fit"); adopted only if it lowers the error on the last 20% ("test"). Headline
    numbers are on the test part with the factor fitted without it; the factor used live is refitted on everything;
  - historical equipment availability is unknown, so outage hours stay in the data (they count as forecast error);
  - the uploaded history is hourly, so DSM 15-minute blocks are downscaled from hourly values on both sides.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from terra.data.build_dataset import build_dataset
from terra.data.openmeteo import OpenMeteoClient
from terra.data.solar_twin import simulate_solar, solar_position
from terra.data.weather_tables import add_derived
from terra.data.wind_twin import simulate_wind
from terra.engines.dsm import DsmProfile, deviation_charges, schedule_at_level
from terra.engines.impact import impact_summary
from terra.engines.trust import trust_features
from terra.engines.value_of_forecast import hybrid_long, run_value_of_forecast
from terra.eval.metrics import metrics_table
from terra.features.framing import frame_source, issue_times
from terra.logs import get_logger
from terra.models.downscale import downscale_solar, downscale_wind
from terra.models.registry import load_object, load_serving_bundle
from terra.profile import Applied
from terra.schema import ACTUAL_VARS, FORECAST_VARS, PHYS, QCOLS

log = get_logger(__name__)
MODELS_OUT = {"ensemble": "Vidyut forecast (served)", "physics": "Physics model", "persistence": "Persistence"}
HISTORY_DAYS = 45


def _weather(applied: Applied, start: pd.Timestamp, end: pd.Timestamp,
             client: OpenMeteoClient) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = applied.model_cfg
    s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    fx = client.fetch_previous_runs(cfg.site.latitude, cfg.site.longitude, s, e, FORECAST_VARS,
                                    model=cfg.weather.forecast_model).interpolate(limit=3)
    for p in ("fx0_", "fx1_", "fx2_"):
        fx = add_derived(fx, p)
    act = client.fetch_archive(cfg.site.latitude, cfg.site.longitude, s, e, ACTUAL_VARS,
                               model=cfg.weather.actual_model).interpolate(limit=3)
    act = add_derived(act, "act_")
    idx = fx.index.intersection(act.index)
    act = act.reindex(idx)
    act["gap_flag"] = act.isna().any(axis=1)
    return act, fx.reindex(idx)


def _ratio(phys_u: np.ndarray, phys_m: np.ndarray, cap_m: float) -> np.ndarray:
    eps = 0.02 * cap_m
    return np.clip((np.nan_to_num(phys_u) + eps) / (np.nan_to_num(phys_m) + eps), 0.0, 4.0)


HALF_LIFE_DAYS = 21.0


def _wratio(y: np.ndarray, f: np.ndarray, t: pd.DatetimeIndex) -> float:
    age = (t.max() - t).total_seconds().to_numpy() / 86400
    w = 0.5 ** (age / HALF_LIFE_DAYS)
    return float(np.clip((w * y).sum() / max((w * f).sum(), 1e-9), 0.3, 1.6))


def _m(y: np.ndarray, p: np.ndarray, cap: float) -> dict:
    ok = np.isfinite(y) & np.isfinite(p)
    if ok.sum() == 0:
        return {"mae_mw": None, "nmae_pct": None, "bias_pct": None, "hours": 0}
    e = p[ok] - y[ok]
    return {"mae_mw": round(float(np.abs(e).mean()), 3), "nmae_pct": round(float(100 * np.abs(e).mean() / cap), 2),
            "bias_pct": round(float(100 * e.sum() / max(y[ok].sum(), 1e-6)), 1), "hours": int(ok.sum())}


def _calibrate(p: pd.DataFrame, s: str, cap: float, nasa: pd.Series | None, act_ghi: pd.Series) -> dict:
    """Fit the calibration factor on the served forecast (day-ahead, lead <= 24)."""
    e = p[(p["model"] == "ensemble") & (p["lead_h"] <= 24)].copy()
    y, f = e["y"].to_numpy(), e["q50"].to_numpy()
    t = pd.DatetimeIndex(e["target_time_utc"])
    active = f > 0.1 * cap
    outage = active & (y < 0.2 * f)                        # likely outage or curtailment, not a forecast error
    fit = (e["split"] == "fit").to_numpy() & active & ~outage & np.isfinite(y)
    test = (e["split"] == "test").to_numpy() & np.isfinite(y) & ~outage
    if s == "solar":
        test &= e["cal_is_day"].to_numpy() == 1
    if fit.sum() < 24 or test.sum() < 12:
        return {"error": "Not enough daylight or windy hours with data to fit.", "factor": 1.0, "adopted": False}
    trial = _wratio(y[fit], f[fit], t[fit])
    before, after = _m(y[test], f[test], cap), _m(y[test], f[test] * trial, cap)
    adopted = after["mae_mw"] < before["mae_mw"]
    allm = active & ~outage & np.isfinite(y)
    factor = _wratio(y[allm], f[allm], t[allm]) if adopted else 1.0
    daily = pd.DataFrame({"measured": y, "forecast": f, "calibrated": f * (trial if adopted else 1.0)}, index=t)
    daily = daily.tz_convert("Asia/Kolkata").resample("1D").sum(min_count=12).dropna()
    res = {"factor": round(factor, 4), "trial_factor": round(trial, 4), "adopted": bool(adopted),
           "fit_hours": int(fit.sum()), "test_hours": int(test.sum()), "excluded_outage_hours": int(outage.sum()),
           "before": before, "after": after,
           "daily_mwh": [{"date": d.strftime("%Y-%m-%d"), **{k: round(float(v), 2) for k, v in r.items()}}
                         for d, r in daily.iterrows()]}
    if s == "solar":
        day = e["cal_is_day"].to_numpy() == 1
        yy = pd.Series(y, index=t)
        res["corr_openmeteo_ghi"] = round(float(yy[day].corr(act_ghi.reindex(t)[day])), 3)
        if nasa is not None:
            n = nasa.reindex(t)
            mm = day & n.notna().to_numpy() & np.isfinite(y)
            if mm.sum() > 24:
                res["corr_nasa_ghi"] = round(float(yy[mm].corr(n[mm])), 3)
                res["nasa_hours"] = int(mm.sum())
    return res


def evaluate_plant(measured: pd.DataFrame, applied: Applied, client: OpenMeteoClient | None = None,
                   nasa: pd.Series | None = None) -> dict:
    """measured: hour-ending UTC index, columns solar_mw and/or wind_mw in the operator's MW."""
    client = client or OpenMeteoClient()
    user, model = applied.user_cfg, applied.model_cfg
    start = measured.index[0] - pd.Timedelta(days=1)
    end = measured.index[-1]
    act, fx = _weather(applied, start, end, client)
    ds = build_dataset(model, act, fx, save=False)
    sp = solar_position(ds.index, user.site)
    srcs = [s for s in ("solar", "wind") if f"{s}_mw" in measured and s in applied.sources]
    if not srcs:
        return {"error": "The upload has no data for the sources this plant has."}

    # Measured history -> the trained plant's MW (inverse physics ratio on actual weather), so the history
    # features the models read are on the scale they were trained on.
    y_user: dict[str, pd.Series] = {}
    for s in ("solar", "wind"):
        if s in srcs:
            y = measured[f"{s}_mw"].reindex(ds.index)
            if s == "solar":
                pu = simulate_solar(ds, user.site, user.solar, "act_", sp)
                pm = simulate_solar(ds, model.site, model.solar, "act_", sp)
            else:
                pu, pm = simulate_wind(ds, user.wind, "act_"), simulate_wind(ds, model.wind, "act_")
            ds[f"{s}_mw"] = (y / _ratio(pu.to_numpy(), pm.to_numpy(), model.capacity_mw(s))).to_numpy()
            y_user[s] = y
        else:
            ds[f"{s}_mw"] = 0.0
            y_user[s] = pd.Series(0.0, index=ds.index)

    issues = issue_times(ds.index, [model.forecast.dayahead_issue_hour_utc], 48, 7 * 24)
    issues = issues[issues <= measured.index[-1] - pd.Timedelta(hours=24)]
    if len(issues) < 5:
        return {"error": "Need at least two weeks of history to evaluate (one week of lead-in plus test days)."}
    cut = issues[int(len(issues) * 0.8)]
    eng = load_object("hybrid", "engines@latest")

    long: dict[str, pd.DataFrame] = {}
    fits: dict[str, dict] = {}
    trust_rows = []
    for s in ("solar", "wind"):
        bundle = load_serving_bundle(s)
        rows = frame_source(ds, s, model, issues, require_target=False)
        q, members, spread = bundle.predict(rows)
        targets = pd.DatetimeIndex(rows["target_time_utc"])
        pu = {d: (simulate_solar(ds, user.site, user.solar, f"fx{d}_", sp) if s == "solar"
                  else simulate_wind(ds, user.wind, f"fx{d}_")) for d in (1, 2)}
        lead = rows["lead_h"].to_numpy()
        phys_u = np.where(lead <= 24, pu[1].reindex(targets).to_numpy(), pu[2].reindex(targets).to_numpy())
        k = _ratio(phys_u, rows[f"{PHYS}mw"].to_numpy(), model.capacity_mw(s))
        on = s in applied.sources
        k = k * (1.0 if on else 0.0)                     # calibration is fitted below, on this uncalibrated forecast
        y = y_user[s].reindex(targets).to_numpy()
        base = rows[["issue_time_utc", "target_time_utc", "lead_h", "lead_bucket", "cal_is_day"]].reset_index(drop=True)
        frames = []
        for name, qq in (("ensemble", q), ("physics", members["physics"]), ("persistence", members["persistence"])):
            f = base.copy()
            f[list(QCOLS)] = qq[list(QCOLS)].to_numpy() * k[:, None]
            f["y"] = y
            f["model"] = name
            frames.append(f)
        p = pd.concat(frames, ignore_index=True)
        p["split"] = np.where(p["issue_time_utc"] < cut, "fit", "test")
        p = p.dropna(subset=["y"])
        if on:
            fits[s] = _calibrate(p, s, user.capacity_mw(s), nasa, ds["act_ghi"])
            kc = fits[s]["trial_factor"] if fits[s].get("adopted") else 1.0
            ens = p["model"] == "ensemble"
            p.loc[ens, list(QCOLS)] = p.loc[ens, list(QCOLS)].to_numpy() * kc
            k = k * kc
        long[s] = p
        if on:
            cap = user.capacity_mw(s)
            absres = (ds[f"{s}_mw"] - ds[f"phys0_{s}_mw"]).abs().rolling(168, min_periods=1).mean()
            recent = absres.reindex(rows["issue_time_utc"]).to_numpy() / bundle.capacity_mw
            qk = q.mul(k, axis=0)
            feats = trust_features(qk, spread * k, lead, recent, cap)
            score = eng["trust"][s].score(feats)
            err = np.abs(y - qk["q50"].to_numpy())
            ok = np.isfinite(err) & (rows["issue_time_utc"].to_numpy() >= cut)
            if s == "solar":
                ok &= rows["cal_is_day"].to_numpy() == 1
            if ok.sum() > 24:
                bins = pd.cut(score[ok], [-1, 40, 70, 101], labels=["low", "medium", "high"])
                trust_rows.append((s, float(spearmanr(score[ok], err[ok]).statistic),
                                   pd.Series(err[ok]).groupby(bins, observed=False).mean().round(3).to_dict()))

    out: dict = {"period": [measured.index[0].isoformat(), measured.index[-1].isoformat()],
                 "test_from": cut.isoformat(), "issues": int(len(issues)), "test_issues": int((issues >= cut).sum()),
                 "sources": srcs, "models": MODELS_OUT, "calibration_fit": fits,
                 "factors": {s: f["factor"] for s, f in fits.items() if f.get("adopted")}}

    # ---- accuracy, same harness as the Dewas evaluation ----
    acc = {}
    for s in srcs:
        cap = user.capacity_mw(s)
        t = long[s][long[s]["split"] == "test"]
        acc[s] = {
            "rows": metrics_table(t, cap, daylight_only=s == "solar").round(4).to_dict(orient="records"),
            "by_lead": metrics_table(t, cap, by=["lead_bucket"], daylight_only=s == "solar")
            .round(4).to_dict(orient="records"),
            "all_hours_rows": metrics_table(t, cap).round(4).to_dict(orient="records"),
        }
    out["accuracy"] = acc
    out["trust"] = {s: {"spearman_score_vs_abs_error": r, "mae_by_level": m} for s, r, m in trust_rows}

    # ---- forecast against measured (day-ahead, lead <= 24) for the history chart ----
    hist = {}
    for s in srcs:
        e = long[s][(long[s]["model"] == "ensemble") & (long[s]["lead_h"] <= 24)].sort_values("target_time_utc")
        e = e[e["target_time_utc"] > e["target_time_utc"].max() - pd.Timedelta(days=HISTORY_DAYS)]
        hist[s] = [{"target_time_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "actual_mw": round(float(a), 3),
                    "q10": round(float(lo), 3), "q50": round(float(m), 3), "q90": round(float(hi), 3)}
                   for t, a, lo, m, hi in zip(e["target_time_utc"], e["y"], e["q10"], e["q50"], e["q90"])]
    out["history"] = hist

    # ---- deviation charges (DSM): day-ahead schedule for the next IST day, test period ----
    prof = DsmProfile.load()
    levels = eng.get("dsm_level", {})
    dsm_rows = []
    for s in srcs:
        cap = user.capacity_mw(s)
        p = long[s][(long[s]["split"] == "test") & long[s]["lead_h"].between(19, 42)]
        fn = (lambda x, c=cap: downscale_solar(x, user.site, c)) if s == "solar" else (lambda x, c=cap: downscale_wind(x, c))
        for strat, model_name, use_level in (("persistence", "persistence", False), ("terra_p50", "ensemble", False),
                                              ("terra_optimized", "ensemble", True)):
            qb, ab = [], []
            for _, g in p[p["model"] == model_name].groupby("issue_time_utc"):
                g = g.sort_values("target_time_utc")
                idx = pd.DatetimeIndex(g["target_time_utc"])
                qb.append(np.column_stack([fn(pd.Series(g[c].to_numpy(), index=idx)).to_numpy() for c in QCOLS]))
                ab.append(fn(pd.Series(g["y"].to_numpy(), index=idx)).to_numpy())
            if not qb:
                continue
            qv, av = np.vstack(qb), np.concatenate(ab)
            sched = schedule_at_level(qv, levels.get(s, 0.5)) if use_level else qv[:, 2]
            ch = deviation_charges(sched, av, cap, s, prof)
            dsm_rows.append({"source": s, "strategy": strat, "charge_inr": round(float(ch["charge_inr"].sum()), 0),
                             "blocks_outside_tolerance_pct": round(float(100 * (ch["beyond_tolerance_pct"] > 0).mean()), 2)})
    out["dsm"] = {"illustrative_rates": prof.illustrative, "chosen_level": {s: levels.get(s, 0.5) for s in srcs},
                  "table": dsm_rows, "note": "15-minute blocks downscaled from hourly values"}

    # ---- value of forecast and impact (battery planned with each forecast, settled on measured output) ----
    try:
        test = {s: long[s][long[s]["split"] == "test"] for s in ("solar", "wind")}
        hour = model.forecast.dayahead_issue_hour_utc
        hyb = {m: hybrid_long(test["solar"], test["wind"], m, eng["rho_by_day"], user, issue_hour=hour, max_lead=24)
               for m in ("persistence", "physics", "ensemble")}
        kdem = user.demand.peak_mw / model.demand.peak_mw
        vof = run_value_of_forecast(hyb, ds["demand_mw"] * kdem, user, horizon_h=24)
        days = hyb["ensemble"]["issue_time_utc"].nunique()
        out["value_of_forecast"] = vof.round(3).to_dict(orient="records")
        out["impact"] = impact_summary(vof, user, pd.DataFrame(dsm_rows), days=days)
    except Exception as exc:  # noqa: BLE001 - impact needs both sources aligned; report why it is missing
        log.warning("plant impact not computed: %s", exc)
        out["impact"] = None
    return out
