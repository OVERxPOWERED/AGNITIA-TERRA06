"""Dataset quality checks. `check_dataset` returns a list of problems (empty list = OK)."""
from __future__ import annotations

import pandas as pd

from terra.config import TerraConfig
from terra.schema import ACT, is_feature


def check_dataset(df: pd.DataFrame, cfg: TerraConfig) -> list[str]:
    problems: list[str] = []
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        problems.append("index must be tz-aware DatetimeIndex")
    if not df.index.is_monotonic_increasing:
        problems.append("index not sorted")
    if df.index.has_duplicates:
        problems.append("duplicate timestamps")
    if len(df) > 1 and (pd.Series(df.index).diff().dropna() != pd.Timedelta(hours=1)).any():
        problems.append("index is not strictly hourly")
    for col, cap in (("solar_mw", cfg.solar.ac_capacity_mw), ("wind_mw", cfg.wind.capacity_mw)):
        s = df[col]
        if s.isna().any():
            problems.append(f"{col} has NaN")
        if (s < -1e-9).any():
            problems.append(f"{col} negative")
        if (s > cap + 1e-6).any():
            problems.append(f"{col} exceeds capacity {cap}")
    night = df["zenith"] >= 90
    if (df.loc[night, "solar_mw"] > 1e-6).any():
        problems.append("solar_mw > 0 at night")
    ranges = {"act_ghi": (0, 1400), "act_t2m": (-10, 55), "act_ws100": (0, 60), "act_rh2m": (0, 100.5)}
    for col, (lo, hi) in ranges.items():
        if col in df and ((df[col] < lo) | (df[col] > hi)).any():
            problems.append(f"{col} outside [{lo}, {hi}]")
    return problems


def assert_no_leakage(feature_cols: list[str]) -> None:
    """Raise if any feature is not an allowed prefix or is actual weather / target."""
    bad = [c for c in feature_cols if c.startswith(ACT) or not is_feature(c)]
    if bad:
        raise AssertionError(f"leaky or unknown feature columns: {bad}")
