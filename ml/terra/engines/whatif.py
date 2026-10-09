"""H4 What-if engine: perturb the latest run's forecast weather / plant and re-forecast + re-dispatch.

Uses physics + LightGBM members only (Chronos-2 is too slow for interactive use; documented).
Capacity changes: physics is recomputed with the new capacity; GBM output is scaled by new/old capacity
(an approximation, documented in the UI).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from terra.config import TerraConfig
from terra.data.solar_twin import simulate_solar
from terra.data.wind_twin import simulate_wind
from terra.engines.dispatch import plan
from terra.engines.hybrid import hybrid_forecast
from terra.schema import QCOLS


class Scenario(BaseModel):
    irradiance_scale: float = Field(1.0, ge=0.2, le=1.3)     # 0.5 = much cloudier than forecast
    wind_scale: float = Field(1.0, ge=0.5, le=1.5)
    solar_ac_mw: float | None = Field(None, gt=0, le=500)
    wind_turbines: int | None = Field(None, gt=0, le=250)
    battery_mw: float | None = Field(None, ge=0, le=500)
    battery_mwh: float | None = Field(None, ge=0, le=2000)


def _apply(rows: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    r = rows.copy()
    for c in ("fx_ghi", "fx_dni", "fx_dhi"):
        r[c] = r[c] * sc.irradiance_scale
    if "fx_csi" in r:
        r["fx_csi"] = (r["fx_csi"] * sc.irradiance_scale).clip(0, 1.5)
    for c in ("fx_ws10", "fx_ws100"):
        r[c] = r[c] * sc.wind_scale
    r["fx_ws100_cubed"] = r["fx_ws100"] ** 3
    return r


def _predict(bundle, rows: pd.DataFrame, scale: float) -> pd.DataFrame:
    members = [m for m in bundle.ensemble.members if m in bundle.models]
    X = rows[bundle.features + ["lead_bucket"]]
    preds = {m: bundle.models[m].predict(X) for m in members}
    preds["gbm"] = preds["gbm"] * scale if "gbm" in preds else preds.get("gbm")
    out = np.zeros((len(rows), len(QCOLS)))
    buckets = rows["lead_bucket"].astype(str).to_numpy()
    for b, w in bundle.ensemble.weights.items():
        idx = [bundle.ensemble.members.index(m) for m in members]
        ww = np.asarray(w)[idx]
        ww = ww / ww.sum()
        sel = buckets == b
        out[sel] = sum(wi * preds[m][list(QCOLS)].to_numpy()[sel] for wi, m in zip(ww, members))
    q = pd.DataFrame(np.sort(out, axis=1), columns=list(QCOLS), index=rows.index)
    return bundle.cqr.apply(q, rows, bundle.capacity_mw * scale, zero_at_night=bundle.source == "solar")


def run_whatif(cfg: TerraConfig, rows: dict[str, pd.DataFrame], bundles: dict, engines: dict,
               demand: np.ndarray, sc: Scenario, plant_factor: dict[str, np.ndarray] | None = None,
               plant_cfg: TerraConfig | None = None) -> dict:
    """`cfg` is the plant the rows were framed for (the trained plant). For an operator's plant pass `plant_cfg`
    and the hourly `plant_factor` the live run used (physics ratio x availability x calibration); scenario
    capacities are then read as the operator's capacities and applied as ratios."""
    pc = plant_cfg or cfg
    r_solar = (sc.solar_ac_mw or pc.solar.ac_capacity_mw) / pc.solar.ac_capacity_mw
    r_wind = (sc.wind_turbines or pc.wind.n_turbines) / pc.wind.n_turbines
    new_solar = cfg.solar.model_copy(update={"ac_capacity_mw": cfg.solar.ac_capacity_mw * r_solar,
                                             "dc_capacity_mw": cfg.solar.dc_capacity_mw * r_solar})
    new_wind = cfg.wind.model_copy(update={"n_turbines": max(1, round(cfg.wind.n_turbines * r_wind))})
    new_bat = pc.battery.model_copy(update={"power_mw": pc.battery.power_mw if sc.battery_mw is None else sc.battery_mw,
                                            "energy_mwh": pc.battery.energy_mwh if sc.battery_mwh is None
                                            else sc.battery_mwh})
    result = {}
    for label, (scn, sol_cfg, wind_cfg, bat, rs, rw) in {
        "before": (Scenario(), cfg.solar, cfg.wind, pc.battery, 1.0, 1.0),
        "after": (sc, new_solar, new_wind, new_bat, r_solar, r_wind),
    }.items():
        q = {}
        for s in ("solar", "wind"):
            r = _apply(rows[s], scn)
            wx = r.set_index(pd.DatetimeIndex(r["target_time_utc"]))
            phys = simulate_solar(wx, cfg.site, sol_cfg, "fx_") if s == "solar" else simulate_wind(wx, wind_cfg, "fx_")
            r["phys_mw"] = phys.to_numpy()
            old = cfg.capacity_mw(s)
            new = sol_cfg.ac_capacity_mw if s == "solar" else wind_cfg.capacity_mw
            q[s] = _predict(bundles[s], r, new / old)
            if plant_factor is not None:
                q[s] = q[s].mul(plant_factor[s], axis=0)
        is_day = rows["solar"]["cal_is_day"].to_numpy()
        hyb = hybrid_forecast(q["solar"], q["wind"], is_day, engines["rho_by_day"],
                              pc.capacity_mw("solar") * rs, pc.capacity_mw("wind") * rw)
        disp = plan(hyb["q50"].to_numpy(), demand, bat, pc.costs, hyb["q10"].to_numpy())
        result[label] = {
            "hybrid": hyb.assign(target_time_utc=rows["solar"]["target_time_utc"].to_numpy()),
            "energy_mwh_p50": float(hyb["q50"].sum()),
            "kpis": disp.kpis,
        }
    return result
