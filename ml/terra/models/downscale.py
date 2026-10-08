"""Hourly (hour-ending) MW -> 96 x 15-minute blocks per day, preserving each hour's energy."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pvlib.location import Location

from terra.config import SiteCfg


def block_index(hourly_index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """15-min block END times covering every hour-ending interval of `hourly_index`."""
    return pd.DatetimeIndex(np.concatenate([hourly_index - pd.Timedelta(minutes=m) for m in (45, 30, 15, 0)])
                            ).sort_values()


def downscale_wind(hourly: pd.Series, capacity: float) -> pd.Series:
    """Linear interpolation between hour mid-points, then rescale so each hour's mean is preserved."""
    blocks = block_index(hourly.index)
    mid_h = hourly.index - pd.Timedelta(minutes=30)
    mid_b = blocks - pd.Timedelta(minutes=7.5)
    vals = np.interp(mid_b.asi8, mid_h.asi8, hourly.to_numpy())
    s = pd.Series(vals, index=blocks)
    return _rescale(s, hourly, capacity)


def downscale_solar(hourly: pd.Series, site: SiteCfg, capacity: float) -> pd.Series:
    """Shape each hour with the 15-min clear-sky GHI profile, scaled to the hourly mean."""
    blocks = block_index(hourly.index)
    loc = Location(site.latitude, site.longitude, tz="UTC", altitude=site.altitude_m)
    cs = loc.get_clearsky(blocks - pd.Timedelta(minutes=7.5), model="ineichen")["ghi"].to_numpy()
    s = pd.Series(cs, index=blocks)
    return _rescale(s, hourly, capacity)


def _rescale(blocks: pd.Series, hourly: pd.Series, capacity: float) -> pd.Series:
    hour_of_block = blocks.index.ceil("h")
    shape_mean = blocks.groupby(hour_of_block).transform("mean").to_numpy()
    target = hourly.reindex(hour_of_block).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        scaled = np.where(shape_mean > 1e-9, blocks.to_numpy() * target / shape_mean, target)
    scaled = np.clip(np.nan_to_num(scaled), 0, capacity)
    return pd.Series(scaled, index=blocks.index, name=hourly.name)
