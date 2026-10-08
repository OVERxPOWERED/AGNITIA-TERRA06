"""Loaders for the real datasets R1–R4 (see ROADMAP v2 §2.3). Each returns a tidy UTC-indexed frame.

Folder layout (downloaded in task T2.1.x; never committed):
  data/external/kaggle_solar/   Plant_1_Generation_Data.csv  Plant_1_Weather_Sensor_Data.csv  (and Plant_2_*)
  data/external/wind_scada/     T1.csv
  data/external/india_hourly/   *.csv | *.xlsx  (Mendeley DOI 10.17632/y58jknpgs8)
  data/external/cea_monthly/    mp_re_monthly.csv (month, source, generation_mu, capacity_mw) — built in T2.1.6
Column names marked [verify] come from public descriptions; confirm them on the real files first.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from terra.logs import get_logger
from terra.paths import DATA_EXTERNAL

log = get_logger(__name__)
IST = "Asia/Kolkata"


def _hourly(df: pd.DataFrame) -> pd.DataFrame:
    """15/10-min -> hour-ending hourly means (label = end of hour)."""
    return df.resample("h", label="right", closed="right").mean()


def load_kaggle_solar(plant: int, base: Path | None = None) -> pd.DataFrame:
    """R1. Columns out: ac_mw, dc_mw, irradiation_wm2, t_amb, t_mod, n_inverters, inverter_outage_frac."""
    base = base or DATA_EXTERNAL / "kaggle_solar"
    gen = pd.read_csv(base / f"Plant_{plant}_Generation_Data.csv")
    wx = pd.read_csv(base / f"Plant_{plant}_Weather_Sensor_Data.csv")
    # [verify] Plant 1 uses "15-05-2020 00:00" (day-first), Plant 2 uses "2020-05-15 00:00:00"
    for d in (gen, wx):
        d["ts"] = pd.to_datetime(d["DATE_TIME"], dayfirst=True, format="mixed").dt.tz_localize(IST).dt.tz_convert("UTC")
    per_ts = gen.groupby("ts").agg(ac_kw=("AC_POWER", "sum"), dc_kw=("DC_POWER", "sum"),
                                   n_inverters=("SOURCE_KEY", "nunique"))
    w = wx.groupby("ts").agg(irr=("IRRADIATION", "mean"), t_amb=("AMBIENT_TEMPERATURE", "mean"),
                             t_mod=("MODULE_TEMPERATURE", "mean"))
    # inverter outage: inverter reports AC == 0 while irradiation is clearly positive
    g = gen.merge(w[["irr"]], left_on="ts", right_index=True, how="left")
    g["down"] = (g["AC_POWER"] <= 0) & (g["irr"] > 0.2)
    outage = g.groupby("ts")["down"].mean().rename("inverter_outage_frac")
    df = per_ts.join(w, how="outer").join(outage, how="left")
    # [verify] IRRADIATION is in kW/m2 (max ~1.2) -> convert to W/m2
    if df["irr"].max() < 5:
        df["irr"] = df["irr"] * 1000
    # [verify] Plant 1 DC_POWER is reported ~10x AC (known quirk) -> rescale if so
    ratio = (df["dc_kw"] / df["ac_kw"]).replace([np.inf, -np.inf], np.nan).median()
    if ratio > 5:
        log.warning("plant %d: DC/AC median ratio %.1f -> dividing DC by 10", plant, ratio)
        df["dc_kw"] = df["dc_kw"] / 10
    out = pd.DataFrame({"ac_mw": df["ac_kw"] / 1000, "dc_mw": df["dc_kw"] / 1000, "irradiation_wm2": df["irr"],
                        "t_amb": df["t_amb"], "t_mod": df["t_mod"], "n_inverters": df["n_inverters"],
                        "inverter_outage_frac": df["inverter_outage_frac"]})
    out.index.name = "ts_utc"
    return _hourly(out)


def load_wind_scada(path: Path | None = None) -> pd.DataFrame:
    """R2 (Kaggle 'Wind Turbine Scada Dataset', 2018, 10-min). Columns out: power_kw, ws_ms, wd_deg, theoretical_kw."""
    path = path or DATA_EXTERNAL / "wind_scada" / "T1.csv"
    df = pd.read_csv(path)
    # [verify] expected columns and date format "01 01 2018 00:00"
    rename = {"Date/Time": "ts", "LV ActivePower (kW)": "power_kw", "Wind Speed (m/s)": "ws_ms",
              "Theoretical_Power_Curve (KWh)": "theoretical_kw", "Wind Direction (°)": "wd_deg"}
    df = df.rename(columns=rename)
    df["ts"] = pd.to_datetime(df["ts"], format="%d %m %Y %H:%M").dt.tz_localize("UTC")   # timezone unknown
    df = df.set_index("ts").sort_index()
    df.index.name = "ts_utc"
    return df[["power_kw", "ws_ms", "wd_deg", "theoretical_kw"]]


def load_india_hourly(base: Path | None = None) -> pd.DataFrame:
    """R3 all-India hourly. Columns out: demand_mw, solar_mw, wind_mw (MW, UTC)."""
    base = base or DATA_EXTERNAL / "india_hourly"
    files = sorted(list(base.glob("*.csv")) + list(base.glob("*.xlsx")))
    if not files:
        raise FileNotFoundError(f"no files in {base}")
    parts = [pd.read_csv(f) if f.suffix == ".csv" else pd.read_excel(f) for f in files]
    df = pd.concat(parts, ignore_index=True)
    cols = {c: c.lower() for c in df.columns}
    find = lambda key: next(c for c, low in cols.items() if key in low)  # noqa: E731  [verify] column names
    ts_col = next(c for c, low in cols.items() if "date" in low or "time" in low)
    out = pd.DataFrame({
        "demand_mw": pd.to_numeric(df[find("demand")], errors="coerce"),
        "solar_mw": pd.to_numeric(df[find("solar")], errors="coerce"),
        "wind_mw": pd.to_numeric(df[find("wind")], errors="coerce"),
    })
    out.index = pd.to_datetime(df[ts_col], dayfirst=True, format="mixed").dt.tz_localize(IST).dt.tz_convert("UTC")
    out.index.name = "ts_utc"
    out = out[~out.index.duplicated()].sort_index()
    log.info("india_hourly: %s .. %s, %d rows", out.index.min(), out.index.max(), len(out))
    return out


def load_cea_mp_monthly(path: Path | None = None) -> pd.DataFrame:
    """R4 hand-built table. Columns: month (YYYY-MM), source (solar|wind), generation_mu, capacity_mw -> + cf."""
    path = path or DATA_EXTERNAL / "cea_monthly" / "mp_re_monthly.csv"
    df = pd.read_csv(path)
    hours = pd.PeriodIndex(df["month"], freq="M").days_in_month * 24
    df["cf"] = df["generation_mu"] * 1000 / (df["capacity_mw"] * hours)
    return df
