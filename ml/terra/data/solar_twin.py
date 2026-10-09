"""Solar digital twin (pvlib): weather -> AC power in MW.

Used three ways:
1. actual weather  -> "true" plant output (before realism layer)          prefix="act_"
2. forecast weather -> physics forecast M1 and the phys_ feature          prefix="fx1_"/"fx2_"/"fx_"
3. what-if scenarios (modified weather / capacity)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pvlib import inverter, irradiance, pvsystem, temperature, tracking
from pvlib.location import Location

from terra.config import SiteCfg, SolarCfg


def solar_position(index: pd.DatetimeIndex, site: SiteCfg) -> pd.DataFrame:
    """Solar position at the middle of each hour-ending interval, re-indexed to `index`."""
    loc = Location(site.latitude, site.longitude, tz="UTC", altitude=site.altitude_m)
    mid = index - pd.Timedelta(minutes=30)
    sp = loc.get_solarposition(mid)
    sp.index = index
    return sp


def clearsky(index: pd.DatetimeIndex, site: SiteCfg) -> pd.DataFrame:
    """Ineichen clear-sky GHI/DNI/DHI (W/m2) for hour-ending index."""
    loc = Location(site.latitude, site.longitude, tz="UTC", altitude=site.altitude_m)
    mid = index - pd.Timedelta(minutes=30)
    cs = loc.get_clearsky(mid, model="ineichen")
    cs.index = index
    return cs


def poa_irradiance(weather: pd.DataFrame, site: SiteCfg, solar: SolarCfg, prefix: str,
                   sp: pd.DataFrame | None = None) -> pd.Series:
    """Plane-of-array global irradiance (W/m2)."""
    sp = solar_position(weather.index, site) if sp is None else sp
    ghi = weather[f"{prefix}ghi"].clip(lower=0).fillna(0)
    if f"{prefix}dni" in weather and f"{prefix}dhi" in weather:
        dni = weather[f"{prefix}dni"].clip(lower=0).fillna(0)
        dhi = weather[f"{prefix}dhi"].clip(lower=0).fillna(0)
    else:  # decompose GHI with Erbs if DNI/DHI are not available
        dec = irradiance.erbs(ghi, sp["zenith"], weather.index - pd.Timedelta(minutes=30))
        dni, dhi = dec["dni"].fillna(0), dec["dhi"].fillna(0)
    dni_extra = irradiance.get_extra_radiation(weather.index - pd.Timedelta(minutes=30))
    dni_extra.index = weather.index
    tilt, azim = solar.tilt_deg, solar.azimuth_deg
    if getattr(solar, "tracking", "fixed") == "single_axis":
        tr = tracking.singleaxis(sp["apparent_zenith"], sp["azimuth"], axis_tilt=0, axis_azimuth=180,
                                 max_angle=60, backtrack=True, gcr=0.35)
        tilt, azim = tr["surface_tilt"].fillna(0), tr["surface_azimuth"].fillna(180)
    poa = irradiance.get_total_irradiance(
        surface_tilt=tilt, surface_azimuth=azim,
        solar_zenith=sp["apparent_zenith"], solar_azimuth=sp["azimuth"],
        dni=dni, ghi=ghi, dhi=dhi, dni_extra=dni_extra, albedo=solar.albedo, model="isotropic",
    )
    return poa["poa_global"].clip(lower=0).fillna(0)


def dc_ac_from_poa(poa_wm2: pd.Series, t_air_c: pd.Series, wind_ms: pd.Series, solar: SolarCfg,
                   t_cell_c: pd.Series | None = None) -> pd.Series:
    """POA irradiance + temperature -> AC MW (PVWatts DC + PVWatts inverter with clipping)."""
    if t_cell_c is None:
        t_cell_c = temperature.faiman(poa_wm2, t_air_c, wind_ms.clip(lower=0.1))
    pdc = pvsystem.pvwatts_dc(poa_wm2, t_cell_c, solar.dc_capacity_mw, solar.gamma_pdc)
    pdc = pdc * (1.0 - solar.system_loss_frac)
    pdc0_inv = solar.ac_capacity_mw / solar.eta_inv_nom     # DC input that gives rated AC output
    pac = inverter.pvwatts(pdc.clip(lower=0), pdc0_inv, eta_inv_nom=solar.eta_inv_nom)
    return pd.Series(np.clip(np.nan_to_num(pac, nan=0.0), 0.0, solar.ac_capacity_mw), index=poa_wm2.index)


def simulate_solar(weather: pd.DataFrame, site: SiteCfg, solar: SolarCfg, prefix: str = "act_",
                   sp: pd.DataFrame | None = None) -> pd.Series:
    """Weather (with <prefix>ghi/dni/dhi/t2m/ws10) -> AC power MW, 0 at night."""
    sp = solar_position(weather.index, site) if sp is None else sp
    poa = poa_irradiance(weather, site, solar, prefix, sp)
    pac = dc_ac_from_poa(poa, weather[f"{prefix}t2m"].ffill().bfill(),
                         weather[f"{prefix}ws10"].ffill().bfill(), solar)
    pac[sp["zenith"].to_numpy() >= 90] = 0.0
    pac.name = "solar_mw"
    return pac
