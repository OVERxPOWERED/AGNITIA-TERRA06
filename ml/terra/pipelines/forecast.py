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
from terra.data.weather_tables import add_derived
from terra.engines.alerts import generate_alerts
from terra.engines.dispatch import no_battery, plan, rule_based
from terra.engines.dsm import schedule_at_level
from terra.engines.hybrid import hybrid_forecast
from terra.engines.trust import hybrid_trust_score, level, trust_features
from terra.features.framing import frame_source
from terra.logs import get_logger
from terra.models.downscale import downscale_solar, downscale_wind
from terra.models.registry import load_object
from terra.paths import ARTIFACTS
from terra.schema import FORECAST_VARS, QCOLS

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


def run_forecast(cfg: TerraConfig, mode: str = "replay", at: str | None = None) -> Path:
    ds, t0 = live_dataset(cfg) if mode == "live" else replay_dataset(cfg, at)
    issues = pd.DatetimeIndex([t0])
    eng = load_object("hybrid", "engines@latest")
    alert_thrs = eng.get("alert_thresholds") if isinstance(eng, dict) else None
    out = RUNS / t0.strftime("%Y%m%dT%H")
    out.mkdir(parents=True, exist_ok=True)

    per_source: dict[str, pd.DataFrame] = {}
    all_alerts = []
    for s in ("solar", "wind"):
        bundle = load_object(s, "bundle@latest")
        rows = frame_source(ds, s, cfg, issues, require_target=False)
        external = {}
        if any(m.startswith("chronos2") for m in bundle.ensemble.members):
            from terra.models.chronos2 import Chronos2Forecaster  # optional heavy dependency
            ckpt = {"chronos2_zs": "amazon/chronos-2",
                    "chronos2_ft": str(ARTIFACTS / "chronos" / "chronos2_ft" / "finetuned-ckpt")}   # [verify] folder
            external = {m: Chronos2Forecaster(model_id=ckpt[m]).predict_issues(ds, s, issues, bundle.capacity_mw)
                        for m in bundle.ensemble.members if m.startswith("chronos2")}
        q, members, spread = bundle.predict(rows, external)
        cap = bundle.capacity_mw
        absres = (ds[f"{s}_mw"] - ds[f"phys0_{s}_mw"]).abs().rolling(168, min_periods=1).mean()
        recent = float(absres.loc[:t0].iloc[-1]) / cap
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
        df["source"] = s
        per_source[s] = df
        rows.to_parquet(out / f"rows_{s}.parquet")
        fc = df.set_index("target_time_utc")
        th_s = alert_thrs.get(s) if alert_thrs else None
        all_alerts += generate_alerts(fc, s, cap, cfg.alerts, t0, trust=fc["trust_score"], thresholds=th_s)

    sol, win = per_source["solar"], per_source["wind"]
    hyb_q = hybrid_forecast(sol[list(QCOLS)], win[list(QCOLS)], sol["cal_is_day"].to_numpy(),
                            eng["rho_by_day"], cfg.capacity_mw("solar"), cfg.capacity_mw("wind"))
    hyb = sol[["target_time_utc", "lead_h", "cal_is_day"]].copy()
    hyb[list(QCOLS)] = hyb_q.to_numpy()
    hyb["trust_score"] = hybrid_trust_score(
        sol["q50"].to_numpy(),
        win["q50"].to_numpy(),
        sol["trust_score"].to_numpy(),
        win["trust_score"].to_numpy(),
    )
    hyb["trust_level"] = [level(x) for x in hyb["trust_score"]]
    hyb["trust_reason"] = np.where(sol["trust_score"] <= win["trust_score"], sol["trust_reason"], win["trust_reason"])
    hyb["source"] = "hybrid"
    demand = ds["demand_mw"].reindex(hyb["target_time_utc"])
    fc = hyb.set_index("target_time_utc")
    th_hyb = alert_thrs.get("hybrid") if alert_thrs else None
    all_alerts += generate_alerts(fc, "hybrid", cfg.capacity_mw("hybrid"), cfg.alerts, t0,
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
        sdf["hybrid"] = sdf.sum(axis=1)
        sdf.rename_axis("block_end_utc").reset_index().to_parquet(out / "dsm_schedule.parquet")

    (out / "alerts.json").write_text(json.dumps([a.to_dict() for a in all_alerts], indent=2))
    meta = {"issue_time_utc": t0.isoformat(), "mode": mode, "created_at": datetime.now(timezone.utc).isoformat(),
            "attribution": ATTRIBUTION, "plant": "TERRA virtual twin", "config_hash": cfg.hash(),
            "n_alerts": len(all_alerts)}
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    (RUNS / "LATEST").write_text(out.name)
    log.info("forecast run written: %s (%d alerts)", out, len(all_alerts))
    return out
