from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.db.models import UserRow
from app.schemas.api import LocationInfo, LocationJob, LocationResult, ProfileBody, ProfileCheck
from app.services import auth
from app.services import locations as svc

router = APIRouter(tags=["locations"])


@router.get("/locations", response_model=list[LocationInfo])
def locations() -> list[LocationInfo]:
    """The allowlist the /location page offers."""
    return svc.list_locations()


@router.post("/locations/{location_id}/forecast", response_model=LocationJob)
def start(location_id: str, user: Annotated[UserRow | None, Depends(auth.optional_user)],
          body: ProfileBody | None = None, force: bool = False):
    """Start (or reuse, if under 30 minutes old) a live forecast for one allowlisted site, with the caller's plant profile."""
    out = svc.submit(location_id, dict(body.values) if body else {}, force,
                     calibration=body.calibration if body else None, keys=body.keys if body else None,
                     user_id=user.id if user else None)
    if out is None:
        raise HTTPException(404, f"unknown location {location_id!r}")
    if isinstance(out, ProfileCheck):
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_PROFILE", "message": "; ".join(f"{k}: {v}" for k, v in out.errors.items())}})
    return out


@router.get("/locations/jobs/{job_id}", response_model=LocationJob)
def status(job_id: str) -> LocationJob:
    j = svc.job(job_id)
    if j is None:
        raise HTTPException(404, "unknown job (the server may have restarted; start it again)")
    return j


@router.get("/locations/jobs/{job_id}/result", response_model=LocationResult)
def result(job_id: str) -> LocationResult:
    r = svc.result(job_id)
    if r is None:
        raise HTTPException(404, "no finished forecast for this job")
    return r


@router.get("/profile/schema")
def profile_schema() -> dict:
    """Fields, steps and defaults that drive the onboarding wizard and the Settings page."""
    return svc.profile_schema()


@router.post("/profile/check", response_model=ProfileCheck)
def profile_check(body: ProfileBody, location_id: str | None = None) -> ProfileCheck:
    """Validate a plant profile and show what it resolves to. Nothing is stored on the server."""
    return svc.check_profile(dict(body.values), location_id)
