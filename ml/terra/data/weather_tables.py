"""Build aligned hourly weather tables (actual + forecast) on one UTC index.

Timestamp convention (Open-Meteo): radiation is the mean over the PRECEDING hour, other variables
are instantaneous at the timestamp. We therefore treat every row as "hour ending at ts_utc", and all
generation values are the mean power over (ts-1h, ts]. Solar geometry uses ts - 30 min.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from terra.config import TerraConfig
from terra.data.openmeteo import OpenMeteoClient
from terra.logs import get_logger
from terra.paths import DATA_INTERIM
from terra.schema import ACTUAL_VARS, FORECAST_VARS

log = get_logger(__name__)
MAX_INTERP_HOURS = 3


def complete_hourly(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(hours=23),
                        freq="h", name="ts_utc")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.reindex(idx)


def fill_gaps(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Interpolate gaps <= 3 h; return (filled, gap_flag) where gap_flag marks longer gaps."""
    missing_before = df.isna().any(axis=1)
    filled = df.interpolate(method="time", limit=MAX_INTERP_HOURS, limit_area="inside")
    gap_flag = filled.isna().any(axis=1)
    log.info("weather rows missing before=%d, after fill=%d", int(missing_before.sum()), int(gap_flag.sum()))
    return filled, gap_flag


def add_derived(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Add air density, wind-direction sin/cos and shear exponent for one prefix (act_, fx0_, ...)."""
    out = df.copy()
    t_k = out[f"{prefix}t2m"] + 273.15
    out[f"{prefix}rho"] = out[f"{prefix}psfc"] * 100.0 / (287.05 * t_k)          # kg/m3
    rad = np.deg2rad(out[f"{prefix}wd100"])
    out[f"{prefix}wd100_sin"] = np.sin(rad)
    out[f"{prefix}wd100_cos"] = np.cos(rad)
    ratio = (out[f"{prefix}ws100"].clip(lower=0.1) / out[f"{prefix}ws10"].clip(lower=0.1))
    out[f"{prefix}shear"] = (np.log(ratio) / np.log(10.0)).clip(0.05, 0.4)
    return out


def gap_report(df: pd.DataFrame) -> pd.DataFrame:
    rep = pd.DataFrame({"missing": df.isna().sum(), "missing_pct": df.isna().mean() * 100})
    return rep.sort_values("missing_pct", ascending=False)


def build_weather_tables(cfg: TerraConfig, client: OpenMeteoClient | None = None,
                         synthetic: bool = False, save: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (actual, forecast) hourly tables with identical index; optionally save Parquet."""
    s, e = cfg.weather.start_date, cfg.weather.end_date
    if synthetic:
        from terra.data.synthetic_weather import synthetic_actual, synthetic_forecast
        actual = synthetic_actual(cfg, s, e)
        forecast = synthetic_forecast(actual)
    else:
        client = client or OpenMeteoClient()
        actual = client.fetch_archive(cfg.site.latitude, cfg.site.longitude, s, e, ACTUAL_VARS,
                                      model=cfg.weather.actual_model)
        forecast = client.fetch_previous_runs(cfg.site.latitude, cfg.site.longitude, s, e, FORECAST_VARS,
                                              model=cfg.weather.forecast_model)
    actual = complete_hourly(actual, s, e)
    forecast = complete_hourly(forecast, s, e)
    actual, act_gap = fill_gaps(actual)
    forecast, fx_gap = fill_gaps(forecast)
    actual = add_derived(actual, "act_")
    for p in ("fx0_", "fx1_", "fx2_"):
        forecast = add_derived(forecast, p)
    actual["gap_flag"] = act_gap | fx_gap
    if save:
        DATA_INTERIM.mkdir(parents=True, exist_ok=True)
        actual.to_parquet(DATA_INTERIM / "weather_actual.parquet")
        forecast.to_parquet(DATA_INTERIM / "weather_forecast.parquet")
        gap_report(pd.concat([actual, forecast], axis=1)).to_csv(DATA_INTERIM / "gap_report.csv")
    return actual, forecast
