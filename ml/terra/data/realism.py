"""Realism layer: turn clean twin output into realistic "measured" generation.

Applied ONLY to generation from ACTUAL weather. Without it, the target would be a deterministic
function of weather and every model would look unrealistically good.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from terra.config import SolarRealismCfg, WindRealismCfg


def ar1(n: int, phi: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    x = np.empty(n)
    x[0] = rng.normal(0, sigma / np.sqrt(max(1 - phi**2, 1e-6)))
    eps = rng.normal(0, sigma, n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + eps[t]
    return x


def event_mask(n: int, rate_per_day: float, mean_hours: float, rng: np.random.Generator) -> np.ndarray:
    """Random events: start prob rate/24 per hour, exponential duration with given mean."""
    mask = np.zeros(n, dtype=bool)
    starts = np.flatnonzero(rng.random(n) < rate_per_day / 24.0)
    for s in starts:
        dur = max(1, int(round(rng.exponential(mean_hours))))
        mask[s:s + dur] = True
    return mask


def apply_solar_realism(solar_mw: pd.Series, precip_mm: pd.Series, cap_mw: float,
                        cfg: SolarRealismCfg, rng: np.random.Generator) -> tuple[pd.Series, pd.DataFrame]:
    n = len(solar_mw)
    noise = ar1(n, cfg.ar1_phi, cfg.ar1_sigma, rng)                 # sub-hourly cloud effects
    # soiling: grows daily, resets after a rainy day
    daily_rain = precip_mm.fillna(0).resample("D").sum()
    soil_daily = np.zeros(len(daily_rain))
    for i in range(1, len(daily_rain)):
        soil_daily[i] = 0.0 if daily_rain.iloc[i - 1] >= cfg.soiling_reset_rain_mm else \
            min(soil_daily[i - 1] + cfg.soiling_rate_per_day, 0.15)
    soiling = pd.Series(soil_daily, index=daily_rain.index).reindex(solar_mw.index, method="ffill").fillna(0).to_numpy()
    outage = event_mask(n, cfg.outage_rate_per_day, cfg.outage_mean_hours, rng)
    mw = solar_mw.to_numpy() * (1 + noise) * (1 - soiling)
    mw = np.where(outage, mw * (1 - cfg.outage_capacity_frac), mw)
    mw = np.clip(mw, 0, cap_mw)
    mw[solar_mw.to_numpy() <= 0] = 0.0
    flags = pd.DataFrame({"solar_outage": outage, "solar_soiling": soiling}, index=solar_mw.index)
    return pd.Series(mw, index=solar_mw.index, name="solar_mw"), flags


def apply_wind_realism(wind_mw: pd.Series, cap_mw: float, cfg: WindRealismCfg,
                       rng: np.random.Generator) -> tuple[pd.Series, pd.DataFrame]:
    n = len(wind_mw)
    x = wind_mw.to_numpy() / cap_mw
    shape = 4 * x * (1 - x) + 0.15 * (x > 0)          # power-curve scatter largest mid-curve
    noise = ar1(n, cfg.ar1_phi, cfg.ar1_sigma, rng) * shape
    outage = event_mask(n, cfg.outage_rate_per_day, cfg.outage_mean_hours, rng)
    curtail = event_mask(n, cfg.curtail_rate_per_day, cfg.curtail_mean_hours, rng)
    mw = wind_mw.to_numpy() * (1 + noise)
    mw = np.where(outage, mw * (1 - cfg.outage_capacity_frac), mw)
    mw = np.where(curtail, np.minimum(mw, cfg.curtail_level_frac * cap_mw), mw)
    mw = np.clip(mw, 0, cap_mw)
    flags = pd.DataFrame({"wind_outage": outage, "wind_curtailed": curtail}, index=wind_mw.index)
    return pd.Series(mw, index=wind_mw.index, name="wind_mw"), flags
