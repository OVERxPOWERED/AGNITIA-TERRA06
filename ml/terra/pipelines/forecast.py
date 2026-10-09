"""Produce one forecast run (live or replay) and write it to artifacts/runs/<issue>/.

live   : weather from the Open-Meteo Forecast API (past 10 days + next 3 days). The virtual plant's
         "measured" history = twin + realism on the latest-run weather for past hours (documented proxy).
replay : uses data/processed/dataset.parquet; targets after the virtual "now" are hidden.

Run directory contents (read by the backend):
  run.json             issue time, mode, models, attribution, created_at
  forecast.parquet     long: source(solar|wind|hybrid), target_time_utc, lead_h, q05..q95, trust_*, member q50s
  rows_solar.parquet, rows_wind.parquet   framed feature rows (used by what-if)
  alerts.json          list of alert dicts
  dispatch.parquet     strategy(advisor|rule|none) x hour schedule;  dispatch_kpis.json
  dsm_schedule.parquet next IST day, 96 blocks, schedule_mw per source
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from terra.config import TerraConfig
from terra.data.build_dataset import build_dataset, load_dataset
from terra.data.openmeteo import ATTRIBUTION, OpenMeteoClient
from terra.data.solar_twin import simulate_solar, solar_position
from terra.data.weather_tables import add_derived
from terra.data.wind_twin import simulate_wind
from terra.engines.alerts import generate_alerts
from terra.engines.dispatch import no_battery, plan, rule_based
from terra.engines.dsm import schedule_at_level
from terra.engines.hybrid import hybrid_forecast
from terra.engines.trust import hybrid_trust_score, level, trust_features
from terra.features.framing import frame_source
from terra.logs import get_logger
from terra.models.downscale import downscale_solar, downscale_wind
from terra.models.registry import load_object, load_serving_bundle, site_alert_thresholds
from terra.paths import ARTIFACTS
from terra.schema import FORECAST_VARS, PHYS, QCOLS

log = get_logger(__name__)
RUNS = ARTIFACTS / "runs"


def live_dataset(cfg: TerraConfig, client: OpenMeteoClient | None = None) -> tuple[pd.DataFrame, pd.Timestamp]:
    client = client or OpenMeteoClient()
    fx = client.fetch_live_forecast(cfg.site.latitude, cfg.site.longitude, FORECAST_VARS,
                                    model=cfg.weather.forecast_model, past_days=10, forecast_days=3)
    fx = fx.interpolate(limit=3)
    for p in ("fx0_", "fx1_", "fx2_"):
        fx = add_derived(fx, p)
    act = fx[[c for c in fx.columns if c.startswith("fx0_")]].rename(columns=lambda c: "act_" + c[4:])
    act["gap_flag"] = False
    ds = build_dataset(cfg, act, fx, save=False)
    now = pd.Timestamp.now(tz="UTC").floor("h")
    ds.loc[ds.index > now, ["solar_mw", "wind_mw"]] = np.nan
    return ds, now


def replay_dataset(cfg: TerraConfig, at: str | None) -> tuple[pd.DataFrame, pd.Timestamp]:
    ds = load_dataset().copy()
    t0 = pd.Timestamp(at, tz="UTC") if at else cfg.splits.bounds()["test"][0] + pd.Timedelta(days=7)
    t0 = t0.floor("h")
    ds.loc[ds.index > t0, ["solar_mw", "wind_mw"]] = np.nan          # hide the future
    return ds, t0


def _physics_ratio(ds: pd.DataFrame, rows: pd.DataFrame, source: str, user: TerraConfig, model: TerraConfig) -> np.ndarray:
    """Hourly physics(operator plant) / physics(trained plant) on the same lead-resolved forecast weather."""
    targets = pd.DatetimeIndex(rows["target_time_utc"])
    sp = solar_position(ds.index, user.site)
    phys_u = {}
    for d in (1, 2):
        pre = f"fx{d}_"
        phys_u[d] = (simulate_solar(ds, user.site, user.solar, pre, sp) if source == "solar"
                     else simulate_wind(ds, user.wind, pre))
    lead = rows["lead_h"].to_numpy()
    pu = np.where(lead <= 24, phys_u[1].reindex(targets).to_numpy(), phys_u[2].reindex(targets).to_numpy())
    pm = rows[f"{PHYS}mw"].to_numpy()
    eps = 0.02 * model.capacity_mw(source)              # smooths dawn/dusk and calm hours where both are ~0
    return np.clip((np.nan_to_num(pu) + eps) / (np.nan_to_num(pm) + eps), 0.0, 4.0)


def run_forecast(cfg: TerraConfig, mode: str = "replay", at: str | None = None, *, runs_dir: Path | None = None,
                 write_latest: bool = True, progress=None, model_cfg: TerraConfig | None = None,
                 adjust=None, second_opinions: bool = False, api_keys: dict | None = None,
                 site_id: str | None = None) -> Path:
    """`runs_dir`/`write_latest` let the /location feature write elsewhere without touching the main LATEST run.
    `progress(step: str)` is called as each stage starts (used by the API for the loading screen).
    `model_cfg` is the plant the models were trained for; `cfg` is the operator's plant. When they differ the models
    run on `model_cfg` and each hour is multiplied by physics(cfg) / physics(model_cfg) on the same forecast weather.
    `adjust` (terra.profile.Applied) adds hourly availability, condition and calibration factors, the generation
    sources and the export limit. `second_opinions` adds other weather models (live mode)."""
    mcfg = model_cfg or cfg
    sources = adjust.sources if adjust is not None else {"solar", "wind"}
    cap_u = {s: cfg.capacity_mw(s) for s in ("solar", "wind")}
    cap_on = {s: (cap_u[s] if s in sources else 0.0) for s in cap_u}
    hyb_cap = max(cap_on["solar"] + cap_on["wind"], 1e-6)
    kdem = cfg.demand.peak_mw / mcfg.demand.peak_mw
    step = progress or (lambda _s: None)
    runs_root = runs_dir or RUNS
    step("weather")
    ds, t0 = live_dataset(mcfg) if mode == "live" else replay_dataset(mcfg, at)
    step("models")
    issues = pd.DatetimeIndex([t0])
    eng = load_object("hybrid", "engines@latest")
    alert_thrs = eng.get("alert_thresholds") if isinstance(eng, dict) else None
    if mode == "live" and (own := site_alert_thresholds(site_id)):      # this site's own thresholds, not Dewas's
        alert_thrs = own
    out = runs_root / t0.strftime("%Y%m%dT%H")
    out.mkdir(parents=True, exist_ok=True)

    per_source: dict[str, pd.DataFrame] = {}
    factors: dict[str, np.ndarray] = {}
    all_alerts = []
    for s in ("solar", "wind"):
        # live forecasts use the multi-site model; the recorded Dewas replay keeps the model its accuracy tables describe
        bundle = load_serving_bundle(s) if mode == "live" else load_object(s, "bundle@latest")
        rows = frame_source(ds, s, mcfg, issues, require_target=False)
        external = {}
        if any(m.startswith("chronos2") for m in bundle.ensemble.members):
            from terra.models.chronos2 import Chronos2Forecaster  # optional heavy dependency
            ckpt = {"chronos2_zs": "amazon/chronos-2",
                    "chronos2_ft": str(ARTIFACTS / "chronos" / "chronos2_ft" / "finetuned-ckpt")}   # [verify] folder
            external = {m: Chronos2Forecaster(model_id=ckpt[m]).predict_issues(ds, s, issues, bundle.capacity_mw)
                        for m in bundle.ensemble.members if m.startswith("chronos2")}
        q, members, spread = bundle.predict(rows, external)
        absres = (ds[f"{s}_mw"] - ds[f"phys0_{s}_mw"]).abs().rolling(168, min_periods=1).mean()
        recent = float(absres.loc[:t0].iloc[-1]) / bundle.capacity_mw
        k = np.ones(len(q))
        if model_cfg is not None:
            k = _physics_ratio(ds, rows, s, cfg, mcfg)
        if adjust is not None:
            k = k * adjust.factor(s, pd.DatetimeIndex(rows["target_time_utc"]), t0)
        factors[s] = k
        if not np.allclose(k, 1.0):
            q = q.mul(k, axis=0)
            spread = spread * k
            members = {m: mq.mul(k, axis=0) for m, mq in members.items()}
        cap = cap_u[s]
        feats = trust_features(q, spread, rows["lead_h"].to_numpy(), np.full(len(q), recent), cap)
        tm = eng["trust"][s]
        df = pd.DataFrame({"target_time_utc": rows["target_time_utc"], "lead_h": rows["lead_h"],
                           "cal_is_day": rows["cal_is_day"]})
        df[list(QCOLS)] = q.to_numpy()
        df["trust_score"] = tm.score(feats)
        df["trust_level"] = [level(x) for x in df["trust_score"]]
        df["trust_reason"] = tm.explain(feats)
        for m, mq in members.items():
            df[f"{m}_q50"] = mq["q50"].to_numpy()
        df["plant_factor"] = k
        df["source"] = s
        per_source[s] = df
        rows.to_parquet(out / f"rows_{s}.parquet")
        if s not in sources:
            continue
        fc = df.set_index("target_time_utc")
        th_s = alert_thrs.get(s) if alert_thrs else None
        kc = cap / bundle.capacity_mw
        if th_s and kc != 1.0:
            th_s = {n: (x * kc if n.endswith("_mw") or n.endswith("_mw_per_h") else x) for n, x in th_s.items()}
        all_alerts += generate_alerts(fc, s, cap, cfg.alerts, t0, trust=fc["trust_score"], thresholds=th_s)

    step("plan")
    sol, win = per_source["solar"], per_source["wind"]
    hyb_q = hybrid_forecast(sol[list(QCOLS)], win[list(QCOLS)], sol["cal_is_day"].to_numpy(),
                            eng["rho_by_day"], cap_u["solar"], cap_u["wind"])
    limit = adjust.export_limit_mw if adjust is not None else None
    export_curtailed = np.zeros(len(hyb_q))
    if limit is not None:
        export_curtailed = np.clip(hyb_q["q50"].to_numpy() - limit, 0, None)
        hyb_q = hyb_q.clip(upper=limit)
    hyb = sol[["target_time_utc", "lead_h", "cal_is_day"]].copy()
    hyb[list(QCOLS)] = hyb_q.to_numpy()
    hyb["export_curtailed_mw"] = export_curtailed
    w_s = sol["q50"].to_numpy() if "solar" in sources else np.zeros(len(sol))
    w_w = win["q50"].to_numpy() if "wind" in sources else np.zeros(len(win))
    hyb["trust_score"] = hybrid_trust_score(w_s, w_w, sol["trust_score"].to_numpy(), win["trust_score"].to_numpy())
    hyb["trust_level"] = [level(x) for x in hyb["trust_score"]]
    hyb["trust_reason"] = np.where(sol["trust_score"] <= win["trust_score"], sol["trust_reason"], win["trust_reason"])
    hyb["source"] = "hybrid"
    demand = ds["demand_mw"].reindex(hyb["target_time_utc"]) * kdem
    fc = hyb.set_index("target_time_utc")
    th_hyb = alert_thrs.get("hybrid") if alert_thrs else None
    khyb = hyb_cap / mcfg.capacity_mw("hybrid")
    if th_hyb and khyb != 1.0:
        th_hyb = {n: (x * khyb if n.endswith("_mw") or n.endswith("_mw_per_h") else x) for n, x in th_hyb.items()}
    all_alerts += generate_alerts(fc, "hybrid", hyb_cap, cfg.alerts, t0,
                                  demand=pd.Series(demand.to_numpy(), index=fc.index), thresholds=th_hyb)
    forecast = pd.concat([sol, win, hyb], ignore_index=True)
    forecast.to_parquet(out / "forecast.parquet")

    # dispatch (advisor vs rule vs none) on hybrid P50
    idx = pd.DatetimeIndex(hyb["target_time_utc"])
    g50, g10, dem = hyb["q50"].to_numpy(), hyb["q10"].to_numpy(), demand.to_numpy()
    strategies = {"advisor": plan(g50, dem, cfg.battery, cfg.costs, g10, index=idx),
                  "rule": rule_based(g50, dem, cfg.battery, cfg.costs, index=idx),
                  "none": no_battery(g50, dem, cfg.costs, index=idx)}
    disp = pd.concat([r.schedule.assign(strategy=k) for k, r in strategies.items()]).rename_axis("target_time_utc")
    disp.reset_index().to_parquet(out / "dispatch.parquet")
    (out / "dispatch_kpis.json").write_text(json.dumps({k: r.kpis for k, r in strategies.items()}, indent=2))

    # day-ahead DSM schedule for the next IST day
    ist_next = (t0.tz_convert("Asia/Kolkata").normalize() + pd.Timedelta(days=1))
    lo, hi = ist_next.tz_convert("UTC"), (ist_next + pd.Timedelta(days=1)).tz_convert("UTC")
    sched = {}
    for s, df in per_source.items():
        d = df[(df["target_time_utc"] > lo) & (df["target_time_utc"] <= hi)]
        if len(d) < 24:
            continue
        lvl = eng.get("dsm_level", {}).get(s, 0.5)
        hourly = pd.Series(schedule_at_level(d[list(QCOLS)].to_numpy(), lvl), index=pd.DatetimeIndex(d["target_time_utc"]))
        cap = cfg.capacity_mw(s)
        sched[s] = downscale_solar(hourly, cfg.site, cap) if s == "solar" else downscale_wind(hourly, cap)
    if sched:
        sdf = pd.DataFrame(sched)
        sdf["hybrid"] = sdf.sum(axis=1) if limit is None else sdf.sum(axis=1).clip(upper=limit)
        sdf.rename_axis("block_end_utc").reset_index().to_parquet(out / "dsm_schedule.parquet")

    # expected output per 15-minute block over the whole horizon (P50), for the deviation watch
    blocks = {}
    for s, df in per_source.items():
        hourly = pd.Series(df["q50"].to_numpy(), index=pd.DatetimeIndex(df["target_time_utc"]))
        cap = cap_u[s]
        blocks[s] = downscale_solar(hourly, cfg.site, cap) if s == "solar" else downscale_wind(hourly, cap)
    bdf = pd.DataFrame(blocks)
    bdf["hybrid"] = bdf.sum(axis=1) if limit is None else bdf.sum(axis=1).clip(upper=limit)
    bdf.rename_axis("block_end_utc").reset_index().to_parquet(out / "blocks_p50.parquet")

    if second_opinions and mode == "live":
        from terra.data.weather_models import disagreement_alerts
        from terra.data.weather_models import second_opinions as fetch_second_opinions
        step("second")
        targets = pd.DatetimeIndex(hyb["target_time_utc"])
        f_s = adjust.factor("solar", targets, t0) if adjust is not None else np.ones(len(targets))
        f_w = adjust.factor("wind", targets, t0) if adjust is not None else np.ones(len(targets))
        table, status = fetch_second_opinions(cfg, targets, f_s, f_w, sources, limit, api_keys)
        if not table.empty:
            table.to_parquet(out / "weather_models.parquet")
            all_alerts += disagreement_alerts(table, hyb_cap, cfg.alerts.weather_disagreement_frac, t0)
        (out / "weather_models.json").write_text(json.dumps(status, indent=2))

    (out / "alerts.json").write_text(json.dumps([a.to_dict() for a in all_alerts], indent=2))
    meta = {"issue_time_utc": t0.isoformat(), "mode": mode, "created_at": datetime.now(timezone.utc).isoformat(),
            "attribution": ATTRIBUTION, "plant": "TERRA virtual twin", "site": cfg.site.name, "config_hash": cfg.hash(),
            "n_alerts": len(all_alerts)}
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    if write_latest:
        (runs_root / "LATEST").write_text(out.name)
    log.info("forecast run written: %s (%d alerts)", out, len(all_alerts))
    return out
