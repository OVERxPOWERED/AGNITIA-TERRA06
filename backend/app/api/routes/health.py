from __future__ import annotations

from fastapi import APIRouter
from terra.config import load_config
from terra.data.openmeteo import ATTRIBUTION

from app.schemas.api import Health, SiteInfo
from app.services import runs
from app.settings import get_settings

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=Health)
def health() -> Health:
    s = get_settings()
    try:
        r = runs.latest()
        return Health(status="ok", version=s.version, mode=s.mode, latest_run=r["name"],
                      latest_issue_time_utc=r["meta"]["issue_time_utc"])
    except runs.NoRunYet:
        return Health(status="no_run_yet", version=s.version, mode=s.mode)


@router.get("/site", response_model=SiteInfo)
def site() -> SiteInfo:
    c = load_config()
    return SiteInfo(name=c.site.name, latitude=c.site.latitude, longitude=c.site.longitude, timezone=c.site.timezone,
                    solar_ac_mw=c.solar.ac_capacity_mw, wind_mw=c.wind.capacity_mw, battery_mw=c.battery.power_mw,
                    battery_mwh=c.battery.energy_mwh, attribution=ATTRIBUTION,
                    plant_note="Virtual digital-twin plant at a real location, calibrated on real data.")
