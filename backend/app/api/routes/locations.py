from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import LocationInfo, LocationJob, LocationResult
from app.services import locations as svc

router = APIRouter(tags=["locations"])


@router.get("/locations", response_model=list[LocationInfo])
def locations() -> list[LocationInfo]:
    """The allowlist the /location page offers."""
    return svc.list_locations()


@router.post("/locations/{location_id}/forecast", response_model=LocationJob)
def start(location_id: str, force: bool = False) -> LocationJob:
    """Start (or reuse, if under 30 minutes old) a live forecast for one allowlisted site."""
    j = svc.submit(location_id, force)
    if j is None:
        raise HTTPException(404, f"unknown location {location_id!r}")
    return j


@router.get("/locations/jobs/{job_id}", response_model=LocationJob)
def status(job_id: str) -> LocationJob:
    j = svc.job(job_id)
    if j is None:
        raise HTTPException(404, "unknown job (the server may have restarted; start it again)")
    return j


@router.get("/locations/{location_id}/forecast", response_model=LocationResult)
def result(location_id: str) -> LocationResult:
    r = svc.result(location_id)
    if r is None:
        raise HTTPException(404, "no finished forecast for this location yet")
    return r
