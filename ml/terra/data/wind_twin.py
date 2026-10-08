"""Wind digital twin: 10 m / 100 m wind -> hub-height wind -> power curve -> farm MW."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from terra.config import WindCfg
from terra.logs import get_logger

log = get_logger(__name__)

# Fallback normalised 2 MW-class power curve (fraction of rated) if windpowerlib lacks the turbine.
GENERIC_CURVE_WS = np.array([0, 2.5, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 25, 25.01])
GENERIC_CURVE_P = np.array([0, 0, 0.01, 0.05, 0.12, 0.22, 0.36, 0.52, 0.68, 0.82, 0.93, 0.98, 1.0, 1.0, 0.0])


@lru_cache(maxsize=8)
def power_curve(turbine_type: str, rated_mw: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (wind_speed m/s, power fraction of rated) for the turbine, falling back to generic."""
    try:
        from windpowerlib import WindTurbine
        t = WindTurbine(hub_height=100, turbine_type=turbine_type)
        pc = t.power_curve.sort_values("wind_speed")
        ws = pc["wind_speed"].to_numpy(float)
        p = pc["value"].to_numpy(float) / (rated_mw * 1e6)     # windpowerlib values are in W
        p = np.clip(p / max(p.max(), 1e-9), 0, 1)              # normalise to 1.0 at rated
        log.info("power curve %s loaded (%d points)", turbine_type, len(ws))
        return ws, p
    except Exception as exc:  # noqa: BLE001 - any failure -> documented fallback
        log.warning("windpowerlib curve for %s unavailable (%s); using generic curve", turbine_type, exc)
        return GENERIC_CURVE_WS, GENERIC_CURVE_P


def hub_height_wind(ws10: pd.Series, ws100: pd.Series, hub_height_m: float) -> pd.Series:
    """Power-law extrapolation with an hourly shear exponent fitted from the 10 m and 100 m speeds."""
    ratio = ws100.clip(lower=0.1) / ws10.clip(lower=0.1)
    alpha = (np.log(ratio) / np.log(10.0)).clip(0.05, 0.4).fillna(0.14)
    return ws100.clip(lower=0) * (hub_height_m / 100.0) ** alpha


def density_corrected(ws: pd.Series, rho: pd.Series | None, rho0: float = 1.225) -> pd.Series:
    """IEC 61400-12 density correction for pitch-regulated turbines."""
    if rho is None:
        return ws
    return ws * (rho.clip(0.9, 1.4).fillna(rho0) / rho0) ** (1.0 / 3.0)


def turbine_power_frac(ws_hub: np.ndarray, wind: WindCfg) -> np.ndarray:
    ws_c, p_c = power_curve(wind.turbine_type, wind.rated_mw)
    frac = np.interp(ws_hub, ws_c, p_c, left=0.0, right=0.0)
    frac[ws_hub >= wind.cut_out_ms] = 0.0
    return frac


def simulate_wind(weather: pd.DataFrame, wind: WindCfg, prefix: str = "act_") -> pd.Series:
    """Weather (with <prefix>ws10, ws100 and optionally rho) -> farm power MW."""
    ws_hub = hub_height_wind(weather[f"{prefix}ws10"], weather[f"{prefix}ws100"], wind.hub_height_m)
    rho = weather.get(f"{prefix}rho")
    ws_eff = density_corrected(ws_hub, rho)
    frac = turbine_power_frac(ws_eff.fillna(0).to_numpy(), wind)
    mw = frac * wind.rated_mw * wind.n_turbines * (1 - wind.wake_loss_frac) * (1 - wind.electrical_loss_frac)
    return pd.Series(mw, index=weather.index, name="wind_mw")
