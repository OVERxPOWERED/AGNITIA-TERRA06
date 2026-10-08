"""Evaluate the engines on held-out data and save the fitted engine objects.

Fits on the val_cal split (copula rho, trust weights, DSM schedule level) and reports on test:
hybrid band coverage, complementarity, trust-vs-error correlation, alert skill,
value of forecast (backup/cost/CO2), DSM charges, impact summary.
Outputs: artifacts/evaluation/*.json|csv, artifacts/models/hybrid/engines/<ver>/, docs/engine-results.md
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from terra.config import TerraConfig
from terra.data.build_dataset import load_dataset
from terra.engines.alerts import alert_thresholds, evaluate_alert_quality
from terra.engines.dsm import DsmProfile, choose_level, deviation_charges, schedule_at_level
from terra.engines.hybrid import complementarity, fit_copula_rho, pit
from terra.engines.impact import impact_summary
from terra.engines.trust import TrustModel, trust_features
from terra.engines.value_of_forecast import hybrid_long, run_value_of_forecast
from terra.eval.metrics import picp
from terra.logs import get_logger
from terra.models.downscale import downscale_solar, downscale_wind
from terra.models.registry import save_object
from terra.paths import ARTIFACTS, DOCS
from terra.schema import QCOLS

log = get_logger(__name__)
KEYS = ["issue_time_utc", "target_time_utc"]


def _load_preds() -> dict[str, pd.DataFrame]:
    return {s: pd.read_parquet(ARTIFACTS / "backtests" / s / "predictions.parquet") for s in ("solar", "wind")}


def fit_rho(preds: dict[str, pd.DataFrame], cfg: TerraConfig) -> dict[int, float]:
    s = preds["solar"].query("model == 'ensemble' and split == 'val_cal'")
    w = preds["wind"].query("model == 'ensemble' and split == 'val_cal'")
    m = s.merge(w, on=KEYS, suffixes=("_s", "_w"))
    u_s = pit(m["y_s"].to_numpy(), m[[f"{c}_s" for c in QCOLS]].to_numpy(), cfg.capacity_mw("solar"))
    u_w = pit(m["y_w"].to_numpy(), m[[f"{c}_w" for c in QCOLS]].to_numpy(), cfg.capacity_mw("wind"))
    return fit_copula_rho(u_s, u_w, m["cal_is_day_s"].to_numpy())


def fit_trust(p: pd.DataFrame, frame_hist: pd.Series, capacity: float) -> tuple[TrustModel, dict]:
    """p = ensemble rows (one source) for one split; frame_hist = hist_absresid_mean168 aligned to p."""
    spread = p["spread"].to_numpy() if "spread" in p else np.zeros(len(p))
    feats = trust_features(p, spread, p["lead_h"].to_numpy(), frame_hist.to_numpy() / capacity, capacity)
    err = np.abs(p["y"].to_numpy() - p["q50"].to_numpy()) / capacity
    return TrustModel().fit(feats, err), {}


def evaluate_all(cfg: TerraConfig) -> dict:
    ds = load_dataset()
    preds = _load_preds()
    out_dir = ARTIFACTS / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict = {}

    # ---- spread (model disagreement) per row: std of member medians -------------------------
    for s, p in preds.items():
        members = p[p["model"].isin(["physics", "gbm", "chronos2_zs", "chronos2_ft"])]
        spread = members.groupby(KEYS)["q50"].std().rename("spread").reset_index()
        preds[s] = p.merge(spread, on=KEYS, how="left").fillna({"spread": 0.0})

    # ---- H1 hybrid ---------------------------------------------------------------------------
    rho = fit_rho(preds, cfg)
    hyb_test = hybrid_long(preds["solar"][preds["solar"]["split"] == "test"],
                           preds["wind"][preds["wind"]["split"] == "test"], "ensemble", rho, cfg)
    results["hybrid"] = {
        "rho_by_day": rho,
        "picp80": picp(hyb_test["y"].to_numpy(), hyb_test["q10"].to_numpy(), hyb_test["q90"].to_numpy()),
        "picp90": picp(hyb_test["y"].to_numpy(), hyb_test["q05"].to_numpy(), hyb_test["q95"].to_numpy()),
        "complementarity_actual": complementarity(ds["solar_mw"], ds["wind_mw"]),
    }

    # ---- H3 trust ----------------------------------------------------------------------------
    trust_models = {}
    for s, p in preds.items():
        hist = ds[f"{s}_mw"] - ds[f"phys0_{s}_mw"]
        absres = hist.abs().rolling(168, min_periods=1).mean()
        cap = cfg.capacity_mw(s)
        e = p[p["model"] == "ensemble"]
        vc, te = e[e["split"] == "val_cal"], e[e["split"] == "test"]
        tm, _ = fit_trust(vc, absres.reindex(vc["issue_time_utc"]).reset_index(drop=True), cap)
        feats = trust_features(te, te["spread"].to_numpy(), te["lead_h"].to_numpy(),
                               absres.reindex(te["issue_time_utc"]).to_numpy() / cap, cap)
        score = tm.score(feats)
        err = np.abs(te["y"].to_numpy() - te["q50"].to_numpy())
        day = te["cal_is_day"].to_numpy() == 1 if s == "solar" else np.ones(len(te), bool)
        rho_s = spearmanr(score[day], err[day]).statistic
        bins = pd.cut(score[day], [-1, 40, 70, 101], labels=["low", "medium", "high"])
        results[f"trust_{s}"] = {"spearman_score_vs_abs_error": float(rho_s),
                                 "mae_by_level": pd.Series(err[day]).groupby(bins, observed=False).mean().round(3).to_dict(),
                                 "weights": tm.weights.round(4).tolist()}
        trust_models[s] = tm

    # ---- alert quality & thresholds (solar, wind, hybrid; daily 00 UTC, 48 h horizon) ------
    thrs = alert_thresholds(ds, cfg)
    sources_test = {
        "solar": preds["solar"][preds["solar"]["split"] == "test"],
        "wind": preds["wind"][preds["wind"]["split"] == "test"],
        "hybrid": hyb_test,
    }
    alerts_eval = evaluate_alert_quality(sources_test, cfg, thrs)
    results["alerts"] = {
        "thresholds": thrs,
        "solar": alerts_eval["solar"],
        "wind": alerts_eval["wind"],
        "hybrid": alerts_eval["hybrid"],
        "low": alerts_eval["hybrid"]["low"],
        "high": alerts_eval["hybrid"]["high"],
    }

    # ---- value of forecast (H2) --------------------------------------------------------------
    hour = cfg.forecast.dayahead_issue_hour_utc
    hyb_by_model = {m: hybrid_long(preds["solar"][preds["solar"]["split"] == "test"],
                                   preds["wind"][preds["wind"]["split"] == "test"], m, rho, cfg,
                                   issue_hour=hour, max_lead=24)
                    for m in ("persistence", "physics", "gbm", "ensemble")}
    vof = run_value_of_forecast(hyb_by_model, ds["demand_mw"], cfg, horizon_h=24)
    vof.to_csv(out_dir / "value_of_forecast.csv", index=False)
    results["value_of_forecast"] = vof.to_dict(orient="records")

    # ---- DSM (H5): per source, day-ahead issue, IST next-day blocks ---------------------------
    prof = DsmProfile.load()
    dsm_rows = []
    levels = {}
    for s in ("solar", "wind"):
        cap = cfg.capacity_mw(s)
        blocks = {}
        for split in ("val_cal", "test"):
            p = preds[s][(preds[s]["split"] == split) & (preds[s]["issue_time_utc"].dt.hour == hour)
                         & (preds[s]["lead_h"].between(19, 42))]
            for model in ("persistence", "ensemble"):
                g = p[p["model"] == model].sort_values(KEYS)
                qb, ab = [], []
                for _, gi in g.groupby("issue_time_utc"):
                    idx = pd.DatetimeIndex(gi["target_time_utc"])
                    ds_fn = (lambda x: downscale_solar(x, cfg.site, cap)) if s == "solar" else \
                        (lambda x: downscale_wind(x, cap))
                    qb.append(np.column_stack([ds_fn(pd.Series(gi[c].to_numpy(), index=idx)).to_numpy() for c in QCOLS]))
                    ab.append(ds_fn(pd.Series(gi["y"].to_numpy(), index=idx)).to_numpy())
                if qb:
                    blocks[(split, model)] = (np.vstack(qb), np.concatenate(ab))
        level, _ = choose_level(*blocks[("val_cal", "ensemble")], cap, s, prof)
        levels[s] = level
        qt, at = blocks[("test", "ensemble")]
        qp, ap = blocks[("test", "persistence")]
        for strat, sched, act in (("persistence", qp[:, 2], ap), ("terra_p50", qt[:, 2], at),
                                  ("terra_optimized", schedule_at_level(qt, level), at)):
            ch = deviation_charges(sched, act, cap, s, prof)
            dsm_rows.append({"source": s, "strategy": strat, "charge_inr": float(ch["charge_inr"].sum()),
                             "blocks_outside_tolerance_pct": float(100 * (ch["beyond_tolerance_pct"] > 0).mean())})
    dsm = pd.DataFrame(dsm_rows)
    dsm.to_csv(out_dir / "dsm.csv", index=False)
    results["dsm"] = {"illustrative_rates": prof.illustrative, "chosen_level": levels,
                      "table": dsm.to_dict(orient="records")}

    # ---- impact -------------------------------------------------------------------------------
    days = hyb_by_model["ensemble"]["issue_time_utc"].nunique()
    results["impact"] = impact_summary(vof, cfg, dsm, days=days)

    save_object({"rho_by_day": rho, "trust": trust_models, "dsm_level": levels, "alert_thresholds": thrs},
                "hybrid", "engines", {"config_hash": cfg.hash(), "results": results})
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    write_engine_doc(results)
    log.info("evaluation done: %s", json.dumps(results["impact"], default=str))
    return results


def write_engine_doc(r: dict) -> None:
    lines = ["# Engine results (test split)", "", "Generated by `terra evaluate`. Do not edit by hand.", ""]
    h = r["hybrid"]
    lines += ["## Hybrid band", f"- PICP80 = {h['picp80']:.3f}, PICP90 = {h['picp90']:.3f}",
              f"- Copula rho (night/day) = {h['rho_by_day']}", "", "## Trust"]
    for s in ("solar", "wind"):
        t = r[f"trust_{s}"]
        lines.append(f"- {s}: Spearman(score, |error|) = {t['spearman_score_vs_abs_error']:.3f}; "
                     f"MAE by level = {t['mae_by_level']}")
    lines += ["", "## Value of forecast (day-ahead plans settled on actual)", "",
              pd.DataFrame(r["value_of_forecast"]).to_markdown(index=False), "",
              "## Deviation Shield" + (" (ILLUSTRATIVE rates)" if r["dsm"]["illustrative_rates"] else ""), "",
              pd.DataFrame(r["dsm"]["table"]).to_markdown(index=False), "",
              "## Alert quality (test split)", "",
              "Data-driven thresholds derived from training split quantiles (P10 low generation, P90 high generation, "
              "P95 hourly ramp; solar daylight-only for generation thresholds). Deduplicated across daily 00:00 UTC "
              "issue times (48 h horizon).", ""]
    alert_rows = []
    thrs = r.get("alerts", {}).get("thresholds", {})
    for s in ("solar", "wind", "hybrid"):
        s_thrs = thrs.get(s, {})
        s_res = r.get("alerts", {}).get(s, {})
        for kind, kind_label in (("low", "LOW"), ("high", "HIGH")):
            k_res = s_res.get(kind, {})
            thr_mw = s_thrs.get(f"{kind}_mw", float("nan"))
            alert_rows.append({
                "source": s,
                "alert": kind_label,
                "threshold_mw": round(thr_mw, 2),
                "precision": round(k_res.get("precision", 0.0), 3),
                "recall": round(k_res.get("recall", 0.0), 3),
                "alert_hours": k_res.get("alert_hours", 0),
                "event_hours": k_res.get("event_hours", 0),
            })
    lines += [pd.DataFrame(alert_rows).to_markdown(index=False), "",
              "## Impact", "",
              "```json", json.dumps(r["impact"], indent=2), "```"]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "engine-results.md").write_text("\n".join(lines))
