"""Calibrate the physics model to a plant's own measured history (onboarding: "upload measured history").

Steps, all reproducible from the uploaded file and public weather:
  1. Parse the CSV (timestamp + solar and/or wind MW), convert to hour-ending UTC, resample to hourly means.
  2. Data-quality report: coverage, gaps, negatives, values above capacity, stuck readings, night-time solar, and a
     timestamp check (cross-correlation with clear-sky irradiance finds timezone or labelling shifts).
  3. Fetch the actual (reanalysis) weather for the same hours from Open-Meteo, plus NASA POWER irradiance as an
     independent second source.
  4. Run the physics twin of the operator's plant on that weather and fit one multiplicative factor per source:
     a recency-weighted energy ratio (half-life HALF_LIFE_DAYS, so the factor reflects the plant's current state
     rather than last season) on the first 80% of the period, excluding likely outage or curtailment hours.
  5. Score physics before and after the factor on the last 20% (time split, never shuffled). The factor is adopted
     only if it lowers the held-out error; it is then refitted on the whole period with the same weighting.
The adopted factor multiplies the live forecast for that source (`Applied.calibration`).
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import requests

from terra.config import TerraConfig
from terra.data.openmeteo import OpenMeteoClient
from terra.data.solar_twin import clearsky, simulate_solar, solar_position
from terra.data.weather_tables import add_derived
from terra.data.wind_twin import simulate_wind
from terra.logs import get_logger
from terra.schema import ACTUAL_VARS

log = get_logger(__name__)

MAX_DAYS = 366
HALF_LIFE_DAYS = 21.0
MIN_HOURS = 24 * 14
NASA_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
TIME_NAMES = ("timestamp", "time", "datetime", "date_time", "ts", "date")


class UploadError(ValueError):
    """A problem with the uploaded file that the user can fix; the message is shown as-is."""


def parse_csv(text: str, tz: str = "Asia/Kolkata", stamp: str = "start", unit: str = "MW",
              interval_min: int | None = None) -> tuple[pd.DataFrame, dict]:
    """CSV text -> hourly frame (hour-ending UTC index; columns solar_mw and/or wind_mw) and parse notes."""
    try:
        raw = pd.read_csv(io.StringIO(text), comment="#")
    except Exception as exc:  # noqa: BLE001
        raise UploadError(f"Could not read the file as CSV ({exc}).") from exc
    cols = {c.lower().strip(): c for c in raw.columns}
    tcol = next((cols[n] for n in TIME_NAMES if n in cols), None)
    if tcol is None:
        raise UploadError("No timestamp column. Name it 'timestamp' (or time / datetime).")
    found = {}
    for src in ("solar", "wind"):
        c = next((cols[n] for n in cols if n.startswith(src)), None)
        if c is not None:
            found[src] = c
    if not found:
        raise UploadError("No generation column. Add 'solar_mw' and/or 'wind_mw'.")
    ts = pd.to_datetime(raw[tcol], errors="coerce")
    bad_ts = int(ts.isna().sum())
    df = pd.DataFrame({f"{s}_mw": pd.to_numeric(raw[c], errors="coerce") for s, c in found.items()})
    df.index = ts
    df = df[df.index.notna()].sort_index()
    if len(df) < 10:
        raise UploadError("Too few readable rows.")
    dup = int(df.index.duplicated().sum())
    df = df[~df.index.duplicated()]
    idx = df.index
    idx = idx.tz_localize(tz, ambiguous="NaT", nonexistent="NaT") if idx.tz is None else idx
    df.index = idx
    df = df[df.index.notna()]
    step = interval_min or int(pd.Series(df.index).diff().dt.total_seconds().div(60).median())
    if step not in (1, 5, 10, 15, 30, 60):
        raise UploadError(f"Readings every {step} minutes are not supported; use 15, 30 or 60-minute data.")
    if unit.lower() == "kw":
        df = df / 1000.0
    if stamp == "start":
        df.index = df.index + pd.Timedelta(minutes=step)
    df.index = df.index.tz_convert("UTC")
    # hour-ending resample: a reading ending at 10:15 belongs to the hour ending 11:00
    hourly = df.resample("1h", label="right", closed="right").mean()
    counts = df.resample("1h", label="right", closed="right").count()
    need = max(1, int(60 / step * 0.75))
    hourly = hourly.where(counts >= need)
    notes = {"rows": int(len(raw)), "unreadable_timestamps": bad_ts, "duplicates_dropped": dup, "interval_min": step,
             "sources": sorted(found), "timezone": tz, "stamp": stamp, "unit": unit}
    if (hourly.index[-1] - hourly.index[0]) > pd.Timedelta(days=MAX_DAYS):
        hourly = hourly[hourly.index > hourly.index[-1] - pd.Timedelta(days=MAX_DAYS)]
        notes["truncated_to_last_days"] = MAX_DAYS
    return hourly, notes


def quality(hourly: pd.DataFrame, cfg: TerraConfig) -> tuple[dict, list[str]]:
    out: dict = {}
    warns: list[str] = []
    span_h = int((hourly.index[-1] - hourly.index[0]) / pd.Timedelta(hours=1)) + 1
    out["first_utc"] = hourly.index[0].isoformat()
    out["last_utc"] = hourly.index[-1].isoformat()
    out["span_days"] = round(span_h / 24, 1)
    sp = solar_position(hourly.index, cfg.site)
    night = sp["zenith"].to_numpy() >= 92
    for s in [c[:-3] for c in hourly.columns]:
        x = hourly[f"{s}_mw"]
        cap = cfg.capacity_mw(s)
        q = {"hours_with_data": int(x.notna().sum()), "coverage_pct": round(100 * x.notna().sum() / span_h, 1),
             "negative_hours": int((x < -0.01 * cap).sum()), "above_capacity_hours": int((x > 1.05 * cap).sum())}
        runs = (x.diff().abs() < 1e-6) & (x > 0.01 * cap)
        q["stuck_hours"] = int(runs.groupby((~runs).cumsum()).transform("sum").ge(6).sum())
        if s == "solar":
            q["night_output_hours"] = int(((x > 0.02 * cap) & night).sum())
            if q["night_output_hours"] > 0.02 * q["hours_with_data"]:
                warns.append("Solar output appears at night. The timezone or the start/end labelling is probably wrong.")
        if q["above_capacity_hours"] > 0:
            warns.append(f"{s.title()} exceeds the plant capacity in {q['above_capacity_hours']} hours: "
                         "check the unit (MW vs kW) or the capacity in Plant settings.")
        if q["coverage_pct"] < 60:
            warns.append(f"{s.title()} data covers only {q['coverage_pct']}% of the period.")
        out[s] = q
    if span_h < MIN_HOURS:
        warns.append("Less than 14 days of data: the calibration will be rough.")
    return out, warns


def timestamp_shift(hourly: pd.DataFrame, cfg: TerraConfig) -> int | None:
    """Lag in hours (-6..6) that best aligns measured solar with clear-sky irradiance; 0 means aligned."""
    if "solar_mw" not in hourly:
        return None
    cs = clearsky(hourly.index, cfg.site)["ghi"]
    x = hourly["solar_mw"]
    best, lag = -2.0, 0
    for k in range(-6, 7):
        c = x.corr(cs.shift(k))
        if c is not None and np.isfinite(c) and c > best:
            best, lag = c, k
    return int(lag)


def fetch_weather(cfg: TerraConfig, start: pd.Timestamp, end: pd.Timestamp,
                  client: OpenMeteoClient | None = None) -> pd.DataFrame:
    client = client or OpenMeteoClient()
    w = client.fetch_archive(cfg.site.latitude, cfg.site.longitude, start.strftime("%Y-%m-%d"),
                             end.strftime("%Y-%m-%d"), ACTUAL_VARS, model=cfg.weather.actual_model)
    return add_derived(w.interpolate(limit=3), "act_")


def fetch_nasa_ghi(cfg: TerraConfig, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series | None:
    """NASA POWER all-sky surface irradiance (W/m2), hour-ending UTC. None if unavailable (it lags by months)."""
    try:
        r = requests.get(NASA_URL, params={"parameters": "ALLSKY_SFC_SW_DWN", "community": "RE",
                                           "latitude": cfg.site.latitude, "longitude": cfg.site.longitude,
                                           "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
                                           "format": "JSON", "time-standard": "UTC"}, timeout=60)
        r.raise_for_status()
        d = r.json()["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    except Exception as exc:  # noqa: BLE001
        log.warning("NASA POWER unavailable: %s", exc)
        return None
    s = pd.Series(d, dtype="float64")
    s.index = pd.to_datetime(s.index, format="%Y%m%d%H", utc=True) + pd.Timedelta(hours=1)   # hour-beginning -> ending
    s = s.where(s > -900)
    return s if s.notna().sum() > 24 else None


def _metrics(y: np.ndarray, p: np.ndarray, cap: float) -> dict:
    m = np.isfinite(y) & np.isfinite(p)
    if m.sum() == 0:
        return {"mae_mw": None, "nmae_pct": None, "bias_pct": None, "hours": 0}
    e = p[m] - y[m]
    return {"mae_mw": round(float(np.abs(e).mean()), 3), "nmae_pct": round(float(100 * np.abs(e).mean() / cap), 2),
            "bias_pct": round(float(100 * e.sum() / max(y[m].sum(), 1e-6)), 1), "hours": int(m.sum())}


def _weighted_ratio(y: pd.Series, phys: pd.Series, mask: pd.Series) -> float:
    """Energy ratio sum(w*y)/sum(w*phys) with weights halving every HALF_LIFE_DAYS back from the last fitted hour."""
    t = y.index[mask.to_numpy()]
    age = (t[-1] - t).total_seconds().to_numpy() / 86400
    w = 0.5 ** (age / HALF_LIFE_DAYS)
    return float(np.clip((w * y[mask].to_numpy()).sum() / max((w * phys[mask].to_numpy()).sum(), 1e-9), 0.3, 1.6))


def calibrate(hourly: pd.DataFrame, cfg: TerraConfig, weather: pd.DataFrame, nasa: pd.Series | None) -> dict:
    """Fit one factor per source; report before/after on the held-out last 20% of the period."""
    idx = hourly.index.intersection(weather.index)
    w = weather.reindex(idx)
    sp = solar_position(idx, cfg.site)
    out: dict = {}
    for s in [c[:-3] for c in hourly.columns]:
        y = hourly[f"{s}_mw"].reindex(idx).clip(lower=0)
        cap = cfg.capacity_mw(s)
        phys = simulate_solar(w, cfg.site, cfg.solar, "act_", sp) if s == "solar" else simulate_wind(w, cfg.wind, "act_")
        ok = y.notna() & phys.notna()
        cut = idx[int(len(idx) * 0.8)] if len(idx) > 10 else idx[-1]
        train = ok & (idx < cut)
        test = ok & (idx >= cut)
        active = phys > 0.1 * cap
        outage = active & (y < 0.2 * phys)                     # likely outage or curtailment: not a model error
        fit = train & active & ~outage
        if fit.sum() < 24:
            out[s] = {"error": "Not enough daylight or windy hours with data to fit."}
            continue
        trial = _weighted_ratio(y, phys, fit)
        day = sp["zenith"] < 90 if s == "solar" else pd.Series(True, index=idx)
        ev = test & day & ~outage
        before = _metrics(y[ev].to_numpy(), phys[ev].to_numpy(), cap)
        after = _metrics(y[ev].to_numpy(), (phys * trial)[ev].to_numpy(), cap)
        adopted = before["mae_mw"] is not None and after["mae_mw"] is not None and after["mae_mw"] < before["mae_mw"]
        factor = _weighted_ratio(y, phys, ok & active & ~outage) if adopted else 1.0
        res = {
            "factor": round(factor, 4), "trial_factor": round(trial, 4), "adopted": bool(adopted),
            "fit_hours": int(fit.sum()), "test_hours": int(ev.sum()),
            "excluded_outage_hours": int((outage & ok).sum()),
            "test_period": [cut.isoformat(), idx[-1].isoformat()],
            "before": before, "after": after,
        }
        if s == "solar":
            res["corr_openmeteo_ghi"] = round(float(y[ok & day].corr(w["act_ghi"][ok & day])), 3)
            if nasa is not None:
                n = nasa.reindex(idx)
                mm = ok & day & n.notna()
                res["corr_nasa_ghi"] = round(float(y[mm].corr(n[mm])), 3) if mm.sum() > 24 else None
                res["nasa_hours"] = int(mm.sum())
        daily = pd.DataFrame({"measured": y, "physics": phys.where(ok), "calibrated": (phys * factor).where(ok)})
        daily = daily.tz_convert("Asia/Kolkata").resample("1D").sum(min_count=12).dropna()
        res["daily_mwh"] = [{"date": d.strftime("%Y-%m-%d"), **{k: round(float(v), 2) for k, v in r.items()}}
                            for d, r in daily.iterrows()]
        out[s] = res
    return out


def run(text: str, cfg: TerraConfig, tz: str = "Asia/Kolkata", stamp: str = "start", unit: str = "MW") -> dict:
    hourly, notes = parse_csv(text, tz, stamp, unit)
    q, warns = quality(hourly, cfg)
    lag = timestamp_shift(hourly, cfg)
    if lag:
        warns.append(f"Solar readings line up best with the sun when shifted by {lag:+d} h. "
                     "Check the timezone and whether timestamps mark the start or the end of each interval.")
    start, end = hourly.index[0] - pd.Timedelta(hours=1), hourly.index[-1]
    weather = fetch_weather(cfg, start, end)
    nasa = fetch_nasa_ghi(cfg, start, end) if "solar_mw" in hourly else None
    fits = calibrate(hourly, cfg, weather, nasa)
    return {"notes": notes, "quality": q, "timestamp_shift_h": lag, "warnings": warns, "sources": fits,
            "factors": {s: r["factor"] for s, r in fits.items() if "factor" in r},
            "weather": {"openmeteo": "archive (reanalysis)",
                        "nasa_power": "ok" if nasa is not None else "unavailable for this period"}}
