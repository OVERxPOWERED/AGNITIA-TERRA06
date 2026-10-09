from __future__ import annotations

from fastapi import APIRouter
from terra.config import load_config
from terra.data.openmeteo import ATTRIBUTION

from app.db import models as db
from app.schemas.api import Health, SiteInfo
from app.services import runs
from app.settings import get_settings

router = APIRouter(tags=["meta"])


@router.api_route("/health", methods=["GET", "HEAD"], response_model=Health)
def health() -> Health:
    """Liveness/readiness probe. Accepts HEAD too: uptime pingers (UptimeRobot) often probe with HEAD."""
    s = get_settings()
    try:
        r = runs.latest()
        return Health(status="ok", version=s.version, mode=s.mode, latest_run=r["name"],
                      latest_issue_time_utc=r["meta"]["issue_time_utc"])
    except runs.NoRunYet:
        return Health(status="no_run_yet", version=s.version, mode=s.mode)


@router.api_route("/health/deep", methods=["GET", "HEAD"])
def health_deep() -> dict:
    """Keep-warm probe: like /health but also makes one tiny query against the database (wakes a suspended
    Neon compute). Always HTTP 200 so a pinger does not page on a slow wake-up; read the `db` field."""
    h = health()
    return {**h.model_dump(), **db.ping()}


@router.get("/site", response_model=SiteInfo)
def site() -> SiteInfo:
    c = load_config()
    return SiteInfo(name=c.site.name, latitude=c.site.latitude, longitude=c.site.longitude, timezone=c.site.timezone,
                    solar_ac_mw=c.solar.ac_capacity_mw, wind_mw=c.wind.capacity_mw, battery_mw=c.battery.power_mw,
                    battery_mwh=c.battery.energy_mwh, attribution=ATTRIBUTION,
                    plant_note="Virtual digital-twin plant at a real location, calibrated on real data.")
