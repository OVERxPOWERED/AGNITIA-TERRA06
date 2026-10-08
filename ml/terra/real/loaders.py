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
import openpyxl
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


def _find_matching_col(
    cols_dict: dict[str, str],
    keywords: tuple[str, ...],
    exclude: tuple[str, ...] = (),
) -> str | None:
    """Find original column name matching any keyword and no exclusions."""
    for low, orig in cols_dict.items():
        if any(k in low for k in keywords) and not any(e in low for e in exclude):
            return orig
    return None


def _parse_india_hourly_table(df: pd.DataFrame) -> pd.DataFrame | None:
    """Parse a single DataFrame into an hourly UTC-indexed DataFrame, or None if layout doesn't match.

    Layout A (5-minute SCADA intervals) is resampled to hourly hour-ending intervals
    (closed='right', label='right') on native IST timestamps before converting to UTC.
    Layout B (already hourly) treats each stamped timestamp as hour-ending and leaves values as-is.
    """
    if df.empty:
        return None

    cols_lower = {str(c).lower(): str(c) for c in df.columns}
    time_col = _find_matching_col(cols_lower, ("time", "date"))
    if time_col is None:
        return None

    # Layout B: headers contain Demand, Wind, Solar
    dem_col = _find_matching_col(cols_lower, ("demand",))
    sol_col = _find_matching_col(cols_lower, ("solar",), exclude=("wind",))
    win_col = _find_matching_col(cols_lower, ("wind",), exclude=("solar",))

    if dem_col is not None and sol_col is not None and win_col is not None:
        ts = pd.to_datetime(df[time_col], errors="coerce", dayfirst=True)
        valid = ts.notna()
        if not valid.any():
            return None
        sub = pd.DataFrame(
            {
                "demand_mw": pd.to_numeric(df.loc[valid, dem_col], errors="coerce").to_numpy(dtype=float),
                "solar_mw": pd.to_numeric(df.loc[valid, sol_col], errors="coerce").to_numpy(dtype=float),
                "wind_mw": pd.to_numeric(df.loc[valid, win_col], errors="coerce").to_numpy(dtype=float),
            },
            index=pd.DatetimeIndex(ts[valid]),
        )
        sub = sub[~sub.index.duplicated(keep="first")].sort_index()
        if len(sub) > 1:
            diffs = sub.index.to_series().diff().dropna()
            if diffs.median() < pd.Timedelta(hours=1):
                sub = sub.resample("h", closed="right", label="right").mean()
        sub.index = sub.index.tz_localize(IST).tz_convert("UTC")
        sub.index.name = "ts_utc"
        return sub

    # Layout A: first data row (row 0) contains SCADA tags e.g. NLDC_DEMAND|P, ALL_IND_SOLAR|P
    if len(df) > 1:
        row0 = df.iloc[0]
        d_tag: str | None = None
        s_tag: str | None = None
        w_tag: str | None = None
        for col, val in row0.items():
            if not isinstance(val, str):
                continue
            vl = val.lower()
            if "demand" in vl:
                d_tag = str(col)
            elif "all_india_wind" in vl:
                w_tag = str(col)
            elif "wind" in vl and "solar" not in vl and w_tag is None:
                w_tag = str(col)
            elif "all_ind_solar" in vl:
                s_tag = str(col)
            elif "solar" in vl and "wind" not in vl and s_tag is None:
                s_tag = str(col)

        if d_tag is not None and s_tag is not None and w_tag is not None:
            data = df.iloc[1:].copy()
            ts = pd.to_datetime(data[time_col], errors="coerce", dayfirst=True)
            valid = ts.notna()
            if not valid.any():
                return None
            sub = pd.DataFrame(
                {
                    "demand_mw": pd.to_numeric(data.loc[valid, d_tag], errors="coerce").to_numpy(
                        dtype=float
                    ),
                    "solar_mw": pd.to_numeric(data.loc[valid, s_tag], errors="coerce").to_numpy(
                        dtype=float
                    ),
                    "wind_mw": pd.to_numeric(data.loc[valid, w_tag], errors="coerce").to_numpy(
                        dtype=float
                    ),
                },
                index=pd.DatetimeIndex(ts[valid]),
            )
            sub = sub[~sub.index.duplicated(keep="first")].sort_index()
            if len(sub) > 1:
                diffs = sub.index.to_series().diff().dropna()
                if diffs.median() < pd.Timedelta(hours=1):
                    sub = sub.resample("h", closed="right", label="right").mean()
            sub.index = sub.index.tz_localize(IST).tz_convert("UTC")
            sub.index.name = "ts_utc"
            return sub

    return None


def _parse_india_hourly_file(path: Path) -> pd.DataFrame:
    """Parse one workbook or CSV file under Layout A or Layout B."""
    if path.suffix == ".xlsx":
        wb = openpyxl.load_workbook(path, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
        for sheet in sheet_names:
            if sheet.lower().startswith("_osi"):
                continue
            df = pd.read_excel(path, sheet_name=sheet)
            sub = _parse_india_hourly_table(df)
            if sub is not None:
                log.info(
                    "india_hourly: parsed %s [sheet '%s'] (%d rows, %s .. %s)",
                    path.name,
                    sheet,
                    len(sub),
                    sub.index.min(),
                    sub.index.max(),
                )
                return sub
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
        sub = _parse_india_hourly_table(df)
        if sub is not None:
            log.info(
                "india_hourly: parsed %s (%d rows, %s .. %s)",
                path.name,
                len(sub),
                sub.index.min(),
                sub.index.max(),
            )
            return sub

    raise ValueError(f"Unrecognized layout in file: {path.name}")


def _mask_implausible(df: pd.DataFrame) -> pd.DataFrame:
    """Mask implausible values in demand and solar columns; clip tare solar noise.

    Rules applied:
    - demand_mw: set to NaN where demand_mw <= 0 or demand_mw < 0.5 * (median demand_mw of that IST calendar month).
    - solar_mw: clip to minimum of 0.0 (inverter tare noise).
    - solar_mw: set to NaN where IST hour is 21..4 (21:00-04:59) and solar_mw > 1500 MW (frozen/corrupt telemetry).
    - wind_mw: untouched.

    Logged per-rule counts. NaNs remain NaN without interpolation or filling.
    """
    if df.empty:
        return df.copy()

    df = df.copy()
    ist_ts = df.index.tz_convert(IST) if df.index.tz is not None else df.index.tz_localize("UTC").tz_convert(IST)

    # 1. Demand masking: <= 0 or < 0.5 * (median demand_mw of that IST calendar month)
    month_key = ist_ts.strftime("%Y-%m")
    monthly_median = df.groupby(month_key)["demand_mw"].transform("median")
    demand_mask = (df["demand_mw"] <= 0) | (df["demand_mw"] < 0.5 * monthly_median)
    n_demand_masked = int(demand_mask.sum())
    df.loc[demand_mask, "demand_mw"] = np.nan

    # 2. Solar tare noise: clip negative values to 0
    solar_neg_mask = df["solar_mw"] < 0
    n_solar_clipped = int(solar_neg_mask.sum())
    df["solar_mw"] = df["solar_mw"].clip(lower=0.0)

    # 3. Night solar spikes: IST 21:00..04:59 with solar_mw > 1500 MW
    is_night = (ist_ts.hour >= 21) | (ist_ts.hour <= 4)
    solar_night_mask = is_night & (df["solar_mw"] > 1500.0)
    n_solar_night_masked = int(solar_night_mask.sum())
    df.loc[solar_night_mask, "solar_mw"] = np.nan

    log.info(
        "india_hourly cleaning: masked %d demand rows (<=0 or <0.5*monthly median), "
        "clipped %d negative solar rows to 0 (tare noise), "
        "masked %d night solar rows (>1500 MW, hours 21..4 IST)",
        n_demand_masked,
        n_solar_clipped,
        n_solar_night_masked,
    )
    return df


def load_india_hourly(base: Path | None = None) -> pd.DataFrame:
    """R3 all-India hourly. Columns out: demand_mw, solar_mw, wind_mw (MW, UTC).

    Layout A (2021-09..2022-09, 13 monthly files) contains 5-minute instantaneous
    telemetry and is resampled to hourly hour-ending intervals using
    closed='right', label='right' (mean power over (ts-1h, ts]) in native IST before
    converting to UTC.

    Layout B (2024-01..2025-06, single workbook) is already hourly and is kept
    unchanged, treating each stamped timestamp directly as the hour-ending value.
    The two layouts therefore differ slightly in physical meaning: Layout A represents
    1-hour interval means, whereas Layout B represents hourly instantaneous/spot telemetry.
    This difference is accepted because both reflect system generation over their respective
    time spans, and both align to the project-wide hour-ending convention (09:00, 10:00]
    for comparison against hour-ending weather forecasts and benchmark evaluations.

    After concatenation, _mask_implausible() cleans unphysical anomalies:
    - demand_mw <= 0 or < 0.5 * (median demand of that IST calendar month) -> NaN
    - solar_mw < 0 clipped to 0.0 (inverter tare noise)
    - solar_mw > 1500 MW during IST night hours 21..4 (21:00-04:59) -> NaN (frozen/corrupt telemetry)
    wind_mw is untouched. NaNs remain NaN without interpolation or filling.
    """
    base = base or DATA_EXTERNAL / "india_hourly"
    all_files = list(base.glob("*.csv")) + list(base.glob("*.xlsx"))
    files = sorted([f for f in all_files if not f.name.startswith("~") and not f.name.startswith(".")])
    if not files:
        raise FileNotFoundError(f"no files in {base}")
    parts = [_parse_india_hourly_file(f) for f in files]
    out = pd.concat(parts)
    out = out[~out.index.duplicated(keep="first")].sort_index()
    out.index.name = "ts_utc"
    out = out.astype({"demand_mw": float, "solar_mw": float, "wind_mw": float})
    out = _mask_implausible(out)
    log.info("india_hourly: total %d rows, %s .. %s", len(out), out.index.min(), out.index.max())
    return out


def load_cea_mp_monthly(path: Path | None = None) -> pd.DataFrame:
    """R4 hand-built table. Columns: month (YYYY-MM), source (solar|wind), generation_mu, capacity_mw -> + cf."""
    path = path or DATA_EXTERNAL / "cea_monthly" / "mp_re_monthly.csv"
    df = pd.read_csv(path)
    hours = pd.PeriodIndex(df["month"], freq="M").days_in_month * 24
    df["cf"] = df["generation_mu"] * 1000 / (df["capacity_mw"] * hours)
    return df
