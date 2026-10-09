"""Second opinions on the weather: several numerical weather models (and optional keyed providers) side by side.

Open-Meteo serves ECMWF IFS, NOAA GFS and DWD ICON through one free, keyless request. Each model's weather is run
through the physics twin of the operator's plant (no ML: the trained models only know one weather source), so the
page can show "what the plant would make if this model is right". When the models disagree by a large share of
capacity, that is a real, explainable source of risk and becomes a WEATHER_DISAGREEMENT alert.

Optional keyed providers (the key comes from the caller and is never stored or logged):
  Solcast     irradiance + temperature forecast   -> solar physics only
  Tomorrow.io 10 m wind speed + temperature       -> wind physics only (100 m wind extrapolated with a 1/7 power law)
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import requests

from terra.config import TerraConfig
from terra.data.openmeteo import FORECAST_URL, OpenMeteoClient
from terra.data.solar_twin import simulate_solar, solar_position
from terra.data.wind_twin import simulate_wind
from terra.engines.alerts import Alert
from terra.logs import get_logger

log = get_logger(__name__)

MODELS = {"ecmwf_ifs025": "ECMWF IFS", "gfs_seamless": "NOAA GFS", "icon_seamless": "DWD ICON"}
VARS = {"shortwave_radiation": "ghi", "direct_normal_irradiance": "dni", "diffuse_radiation": "dhi",
        "temperature_2m": "t2m", "wind_speed_10m": "ws10", "wind_speed_100m": "ws100"}
TIMEOUT_S = 20


def fetch_openmeteo_models(lat: float, lon: float, client: OpenMeteoClient | None = None) -> dict[str, pd.DataFrame]:
    """One request, three models -> {model id: frame with w_ghi, w_dni, w_dhi, w_t2m, w_ws10, w_ws100}."""
    client = client or OpenMeteoClient()
    params = {"latitude": lat, "longitude": lon, "hourly": ",".join(VARS), "models": ",".join(MODELS),
              "forecast_days": 3, "past_days": 1, "wind_speed_unit": "ms", "timezone": "GMT"}
    payload = client.get_live(FORECAST_URL, params)
    h = payload["hourly"]
    idx = pd.to_datetime(h["time"], utc=True)
    out = {}
    for m in MODELS:
        cols = {f"w_{short}": h.get(f"{var}_{m}") for var, short in VARS.items()}
        if any(v is None for v in cols.values()):
            log.warning("weather model %s missing variables; skipped", m)
            continue
        df = pd.DataFrame(cols, index=idx).astype("float64").interpolate(limit=3)
        if df["w_ghi"].notna().sum() > 0:
            out[m] = df
    return out


def fetch_solcast(lat: float, lon: float, key: str) -> pd.DataFrame:
    """Solcast radiation-and-weather forecast (hour-ending, UTC). Raises on HTTP errors."""
    r = requests.get("https://api.solcast.com.au/data/forecast/radiation_and_weather",
                     params={"latitude": lat, "longitude": lon, "hours": 72, "period": "PT60M", "format": "json",
                             "output_parameters": "ghi,dni,dhi,air_temp"},
                     headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT_S)
    r.raise_for_status()
    rows = r.json()["forecasts"]
    idx = pd.to_datetime([x["period_end"] for x in rows], utc=True).floor("h")
    df = pd.DataFrame({"w_ghi": [x.get("ghi") for x in rows], "w_dni": [x.get("dni") for x in rows],
                       "w_dhi": [x.get("dhi") for x in rows], "w_t2m": [x.get("air_temp") for x in rows]}, index=idx)
    df["w_ws10"], df["w_ws100"] = np.nan, np.nan
    return df.astype("float64")


def fetch_tomorrow(lat: float, lon: float, key: str) -> pd.DataFrame:
    """Tomorrow.io hourly forecast: wind speed (10 m) and temperature. Raises on HTTP errors."""
    r = requests.get("https://api.tomorrow.io/v4/weather/forecast",
                     params={"location": f"{lat},{lon}", "timesteps": "1h", "units": "metric", "apikey": key},
                     headers={"accept-encoding": "deflate, gzip, br"}, timeout=TIMEOUT_S)
    r.raise_for_status()
    rows = r.json()["timelines"]["hourly"]
    # Tomorrow.io stamps the start of each hour; our convention is hour-ending.
    idx = pd.to_datetime([x["time"] for x in rows], utc=True) + pd.Timedelta(hours=1)
    ws10 = np.array([x["values"].get("windSpeed", np.nan) for x in rows], dtype=float)
    df = pd.DataFrame({"w_ws10": ws10, "w_ws100": ws10 * 10 ** (1 / 7),
                       "w_t2m": [x["values"].get("temperature", np.nan) for x in rows]}, index=idx)
    df["w_ghi"] = df["w_dni"] = df["w_dhi"] = np.nan
    return df.astype("float64")


def physics_by_model(frames: dict[str, pd.DataFrame], cfg: TerraConfig, targets: pd.DatetimeIndex,
                     factor_solar: np.ndarray, factor_wind: np.ndarray, sources: set[str],
                     export_limit_mw: float | None) -> pd.DataFrame:
    """Long table: target_time_utc, model, ghi, ws100, solar_mw, wind_mw, hybrid_mw (physics only, operator plant)."""
    rows = []
    sp = solar_position(targets, cfg.site)
    for m, df in frames.items():
        w = df.reindex(targets)
        solar = np.full(len(targets), np.nan)
        wind = np.full(len(targets), np.nan)
        if "solar" in sources and w["w_ghi"].notna().sum() > len(targets) // 2:
            ww = w.copy()
            ww["w_ws10"] = ww["w_ws10"].fillna(2.0)
            solar = simulate_solar(ww.ffill().bfill(), cfg.site, cfg.solar, "w_", sp).to_numpy() * factor_solar
        if "wind" in sources and w["w_ws10"].notna().sum() > len(targets) // 2:
            wind = simulate_wind(w.ffill().bfill(), cfg.wind, "w_").to_numpy() * factor_wind
        if "solar" not in sources:
            solar = np.zeros(len(targets))
        if "wind" not in sources:
            wind = np.zeros(len(targets))
        hyb = solar + wind
        if export_limit_mw is not None:
            hyb = np.minimum(hyb, export_limit_mw)
        rows.append(pd.DataFrame({"target_time_utc": targets, "model": m, "ghi": w["w_ghi"].to_numpy(),
                                  "ws100": w["w_ws100"].to_numpy(), "solar_mw": solar, "wind_mw": wind,
                                  "hybrid_mw": hyb}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def disagreement_alerts(table: pd.DataFrame, hybrid_cap_mw: float, frac: float, issue: pd.Timestamp,
                        min_hours: int = 2) -> list[Alert]:
    """One alert per run of >= min_hours where the models' hybrid output spans more than frac x capacity."""
    if table.empty or table["model"].nunique() < 2:
        return []
    wide = table.pivot_table(index="target_time_utc", columns="model", values="hybrid_mw")
    lo, hi = wide.min(axis=1), wide.max(axis=1)
    rng = (hi - lo).to_numpy()
    mask = rng > frac * hybrid_cap_mw
    out, start = [], None
    times = wide.index
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        if not m and start is not None:
            if i - start >= min_hours:
                seg = slice(start, i)
                k = start + int(np.argmax(rng[seg]))
                t0, t1 = times[start], times[i - 1]
                aid = hashlib.sha1(f"WD|{issue}|{t0}".encode()).hexdigest()[:12]
                worst = rng[k] / hybrid_cap_mw
                out.append(Alert(
                    id=aid, type="WEATHER_DISAGREEMENT", source="hybrid",
                    start_utc=(t0 - pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_utc=t1.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    severity="warning" if worst > 2 * frac else "info", probability=float(min(1.0, worst / (2 * frac))),
                    magnitude_mw=float(rng[k]),
                    message=(f"Weather models disagree: plant output between {lo.iloc[k]:.0f} and {hi.iloc[k]:.0f} MW "
                             f"depending on the model ({rng[k]:.0f} MW apart)"),
                    issue_time_utc=issue.strftime("%Y-%m-%dT%H:%M:%SZ")))
            start = None
    return out


def second_opinions(cfg: TerraConfig, targets: pd.DatetimeIndex, factor_solar: np.ndarray, factor_wind: np.ndarray,
                    sources: set[str], export_limit_mw: float | None, keys: dict[str, str] | None = None
                    ) -> tuple[pd.DataFrame, dict[str, str]]:
    """All available weather sources -> physics table, plus a status per source ("ok" or why it was skipped)."""
    status: dict[str, str] = {}
    frames: dict[str, pd.DataFrame] = {}
    try:
        frames.update(fetch_openmeteo_models(cfg.site.latitude, cfg.site.longitude))
        for m in MODELS:
            status[m] = "ok" if m in frames else "no data"
    except Exception as exc:  # noqa: BLE001
        log.warning("open-meteo multi-model request failed: %s", exc)
        for m in MODELS:
            status[m] = f"unavailable ({type(exc).__name__})"
    for name, fn in (("solcast", fetch_solcast), ("tomorrow", fetch_tomorrow)):
        key = (keys or {}).get(name)
        if not key:
            continue
        try:
            frames[name] = fn(cfg.site.latitude, cfg.site.longitude, key)
            status[name] = "ok"
        except requests.HTTPError as exc:
            status[name] = f"rejected (HTTP {exc.response.status_code})"
        except Exception as exc:  # noqa: BLE001
            status[name] = f"unavailable ({type(exc).__name__})"
    table = physics_by_model(frames, cfg, targets, factor_solar, factor_wind, sources, export_limit_mw)
    return table, status


LABELS = {**MODELS, "solcast": "Solcast", "tomorrow": "Tomorrow.io"}
