"""Synthetic but physically plausible weather for tests, CI and offline development.

NOT used for reported results. It lets the full pipeline run without network access.
Forecast columns = actual + lead-dependent error, so models face realistic forecast error.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pvlib import irradiance
from pvlib.location import Location

from terra.config import TerraConfig
from terra.schema import OPENMETEO_VARS


def _ar1(n: int, phi: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    x = np.empty(n)
    x[0] = rng.normal(0, sigma / np.sqrt(1 - phi**2))
    eps = rng.normal(0, sigma, n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + eps[t]
    return x


def synthetic_actual(cfg: TerraConfig, start: str, end: str, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(hours=23),
                        freq="h", name="ts_utc")
    n = len(idx)
    loc = Location(cfg.site.latitude, cfg.site.longitude, tz="UTC", altitude=cfg.site.altitude_m)
    mid = idx - pd.Timedelta(minutes=30)
    sp = loc.get_solarposition(mid)
    cs = loc.get_clearsky(mid, model="ineichen", solar_position=sp)
    doy = idx.dayofyear.to_numpy()
    monsoon = np.exp(-0.5 * ((doy - 200) / 35.0) ** 2)            # Jun-Sep peak
    # cloudiness: AR(1) + monsoon mean
    cloud_latent = _ar1(n, 0.95, 0.25, rng) + 2.2 * monsoon - 0.6
    cloud = 100 / (1 + np.exp(-2.0 * cloud_latent))
    csi = np.clip(1.0 - 0.75 * (cloud / 100) ** 1.5 + rng.normal(0, 0.03, n), 0.05, 1.05)
    ghi = cs["ghi"].to_numpy() * csi
    zen = sp["zenith"].to_numpy()
    erbs = irradiance.erbs(ghi, zen, mid)
    hour_ist = ((idx.hour + 5.5) % 24).to_numpy()
    t2m = 27 + 6 * np.sin(2 * np.pi * (doy - 80) / 365) - 4 * monsoon + 6 * np.sin(2 * np.pi * (hour_ist - 9) / 24) \
        + _ar1(n, 0.97, 0.4, rng)
    rh = np.clip(40 + 40 * monsoon + 0.3 * cloud - 1.2 * (t2m - 27) + rng.normal(0, 4, n), 5, 100)
    psfc = 950 - 4 * monsoon + _ar1(n, 0.99, 0.3, rng)
    # wind: monsoon-driven, stronger at night at 100 m
    ws_mean = 4.5 + 4.0 * monsoon + 0.8 * np.cos(2 * np.pi * (hour_ist - 2) / 24)
    ws100 = np.clip(ws_mean * np.exp(_ar1(n, 0.93, 0.12, rng)), 0.2, 30)
    alpha = np.clip(0.18 + 0.08 * np.cos(2 * np.pi * (hour_ist - 2) / 24), 0.05, 0.4)
    ws10 = ws100 * (10 / 100) ** alpha
    wd100 = (250 + 30 * monsoon + np.cumsum(rng.normal(0, 4, n))) % 360
    precip = np.where(rng.random(n) < 0.02 + 0.15 * monsoon * (cloud / 100), rng.gamma(1.2, 3.0, n), 0.0)
    df = pd.DataFrame({
        "act_ghi": ghi, "act_dni": erbs["dni"].fillna(0).to_numpy(), "act_dhi": erbs["dhi"].fillna(0).to_numpy(),
        "act_cloud": cloud, "act_t2m": t2m, "act_rh2m": rh, "act_psfc": psfc, "act_ws10": ws10,
        "act_ws100": ws100, "act_wd100": wd100, "act_precip": precip,
    }, index=idx)
    return df


def synthetic_forecast(actual: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """fx0/fx1/fx2 = actual + error growing with lead (day0 small, day2 large)."""
    rng = np.random.default_rng(seed)
    n = len(actual)
    out = {}
    for d, scale in ((0, 0.5), (1, 1.0), (2, 1.4)):
        e_cloud = _ar1(n, 0.9, 6 * scale, rng)
        e_ws = _ar1(n, 0.9, 0.08 * scale, rng)
        e_t = _ar1(n, 0.9, 0.5 * scale, rng)
        cloud = np.clip(actual["act_cloud"].to_numpy() + e_cloud, 0, 100)
        ratio = np.clip(1 - 0.75 * (cloud / 100) ** 1.5, 0.05, 1.05) / \
            np.clip(1 - 0.75 * (actual["act_cloud"].to_numpy() / 100) ** 1.5, 0.05, 1.05)
        for v in OPENMETEO_VARS:
            a = actual[f"act_{v}"].to_numpy()
            if v in ("ghi", "dni", "dhi"):
                val = np.clip(a * ratio * (1 + rng.normal(0, 0.03 * scale, n)), 0, None)
            elif v == "cloud":
                val = cloud
            elif v in ("ws10", "ws100"):
                val = np.clip(a * np.exp(e_ws), 0, None)
            elif v == "t2m":
                val = a + e_t
            elif v == "wd100":
                val = (a + rng.normal(0, 15 * scale, n)) % 360
            elif v == "precip":
                val = np.clip(a * rng.lognormal(0, 0.5 * scale, n), 0, None)
            else:
                val = a + rng.normal(0, 0.02 * scale * np.nanstd(a), n)
            out[f"fx{d}_{v}"] = val
    return pd.DataFrame(out, index=actual.index)
