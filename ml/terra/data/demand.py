"""Demand / contracted-load profile for the supply-demand gap and dispatch engines.

parametric  : morning + evening peaks, weekday effect, temperature sensitivity
india_hourly: normalised real all-India hourly demand shape (dataset R3), scaled to peak_mw
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from terra.config import DemandCfg


def _gauss(x: np.ndarray, mu: float, sd: float) -> np.ndarray:
    d = np.minimum(np.abs(x - mu), 24 - np.abs(x - mu))          # circular hour distance
    return np.exp(-0.5 * (d / sd) ** 2)


def parametric_shape(index_utc: pd.DatetimeIndex) -> np.ndarray:
    ist = index_utc.tz_convert("Asia/Kolkata")
    h = (ist.hour + ist.minute / 60).to_numpy(float)
    shape = 0.72 + 0.14 * _gauss(h, 10, 2.5) + 0.22 * _gauss(h, 20, 2.2) - 0.06 * _gauss(h, 3.5, 2.5)
    shape *= np.where(ist.dayofweek.to_numpy() == 6, 0.93, 1.0)                     # Sunday
    shape *= 1 + 0.06 * np.sin(2 * np.pi * (ist.dayofyear.to_numpy() - 60) / 365)  # summer high
    return shape / shape.max()


def shape_from_real(index_utc: pd.DatetimeIndex, real_demand_mw: pd.Series) -> np.ndarray:
    """Average normalised real demand by (month, is_sunday, IST hour) and map onto index."""
    r = real_demand_mw.dropna()
    ist = r.index.tz_convert("Asia/Kolkata")
    norm = r / r.groupby(ist.to_period("M")).transform("max")
    key = pd.MultiIndex.from_arrays([ist.month, ist.dayofweek == 6, ist.hour])
    table = norm.groupby(key).mean()
    tgt = index_utc.tz_convert("Asia/Kolkata")
    k2 = pd.MultiIndex.from_arrays([tgt.month, tgt.dayofweek == 6, tgt.hour])
    vals = table.reindex(k2).to_numpy()
    return np.nan_to_num(vals, nan=float(np.nanmean(vals)))


def demand_profile(index_utc: pd.DatetimeIndex, cfg: DemandCfg, t2m_c: pd.Series | None,
                   rng: np.random.Generator, real_demand_mw: pd.Series | None = None) -> pd.Series:
    if cfg.shape_source == "india_hourly" and real_demand_mw is not None:
        shape = shape_from_real(index_utc, real_demand_mw)
    else:
        shape = parametric_shape(index_utc)
    load = cfg.peak_mw * shape
    if t2m_c is not None:
        load *= 1 + cfg.temp_coeff_per_c * np.clip(t2m_c.to_numpy() - 25.0, 0, None)
    load *= 1 + rng.normal(0, cfg.noise_std_frac, len(load))
    return pd.Series(np.clip(load, 0, None), index=index_utc, name="demand_mw")
