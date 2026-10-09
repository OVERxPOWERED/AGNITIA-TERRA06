"""Assemble data/processed/dataset.parquet: weather + twin targets + physics-on-forecast + demand.

Columns written (see .agent/context/data-contracts.md):
  act_*                     actual weather (analysis only, NEVER a feature)
  fx0_*, fx1_*, fx2_*       forecast weather at previous_day0/1/2 (fx0 for hist residuals, fx1/fx2 for framed leads)
  solar_mw, wind_mw         targets (twin on actual weather + realism layer)
  twin_solar_mw, twin_wind_mw  clean twin output before realism (diagnostics only)
  phys{0,1,2}_solar_mw, phys{0,1,2}_wind_mw  physics model on fx{0,1,2} weather
  demand_mw                 demand / contracted load
  cs_ghi, zenith            clear-sky GHI and solar zenith (deterministic)
  flags: gap_flag, solar_outage, solar_soiling, wind_outage, wind_curtailed
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from terra.config import TerraConfig
from terra.data.demand import demand_profile
from terra.data.realism import apply_solar_realism, apply_wind_realism
from terra.data.solar_twin import clearsky, simulate_solar, solar_position
from terra.data.wind_twin import simulate_wind
from terra.logs import get_logger
from terra.paths import DATA_PROCESSED, DATA_SAMPLES

log = get_logger(__name__)


def build_dataset(cfg: TerraConfig, actual: pd.DataFrame, forecast: pd.DataFrame,
                  real_demand_mw: pd.Series | None = None, save: bool = True, state_scale: bool = True) -> pd.DataFrame:
    assert actual.index.equals(forecast.index), "actual and forecast must share the same index"
    rng = np.random.default_rng(cfg.realism.seed)
    idx = actual.index
    sp = solar_position(idx, cfg.site)
    cs = clearsky(idx, cfg.site)

    twin_solar = simulate_solar(actual, cfg.site, cfg.solar, "act_", sp)
    twin_wind = simulate_wind(actual, cfg.wind, "act_")

    # monthly scaling to Madhya Pradesh official capacity factors (task T2.5.3)
    from terra.config import load_yaml
    try:     # Madhya Pradesh calibration: only meaningful for the Dewas site
        scales = load_yaml("calibration/state.yaml").get("monthly_scale", {}) if state_scale else {}
    except FileNotFoundError:
        scales = {}
    months = idx.tz_convert("Asia/Kolkata").month
    if scales.get("solar"):
        f = pd.Series(months).map(scales["solar"]).fillna(1.0).to_numpy()
        twin_solar = (twin_solar * f).clip(upper=cfg.solar.ac_capacity_mw)
    if scales.get("wind"):
        f = pd.Series(months).map(scales["wind"]).fillna(1.0).to_numpy()
        twin_wind = (twin_wind * f).clip(upper=cfg.wind.capacity_mw)

    solar_mw, s_flags = apply_solar_realism(twin_solar, actual["act_precip"], cfg.solar.ac_capacity_mw,
                                            cfg.realism.solar, rng)
    wind_mw, w_flags = apply_wind_realism(twin_wind, cfg.wind.capacity_mw, cfg.realism.wind, rng)

    phys = {}
    for d in (0, 1, 2):
        phys[f"phys{d}_solar_mw"] = simulate_solar(forecast, cfg.site, cfg.solar, f"fx{d}_", sp)
        phys[f"phys{d}_wind_mw"] = simulate_wind(forecast, cfg.wind, f"fx{d}_")

    demand = demand_profile(idx, cfg.demand, actual["act_t2m"], rng, real_demand_mw)

    df = pd.concat([
        actual, forecast,
        solar_mw, wind_mw,
        twin_solar.rename("twin_solar_mw"), twin_wind.rename("twin_wind_mw"),
        pd.DataFrame(phys, index=idx),
        demand,
        cs["ghi"].rename("cs_ghi"), sp["zenith"].rename("zenith"),
        s_flags, w_flags,
    ], axis=1)
    df.index.name = "ts_utc"
    log.info("dataset built: %d rows, %d cols, solar CF=%.3f wind CF=%.3f", len(df), df.shape[1],
             df["solar_mw"].mean() / cfg.solar.ac_capacity_mw, df["wind_mw"].mean() / cfg.wind.capacity_mw)
    if save:
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        df.to_parquet(DATA_PROCESSED / "dataset.parquet")
        DATA_SAMPLES.mkdir(parents=True, exist_ok=True)
        df.iloc[: 24 * 21].to_parquet(DATA_SAMPLES / "dataset_sample.parquet")   # 3 weeks for tests
    return df


def load_dataset() -> pd.DataFrame:
    return pd.read_parquet(DATA_PROCESSED / "dataset.parquet")
