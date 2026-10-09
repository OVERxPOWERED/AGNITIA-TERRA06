"""Optional login and the signed-in user's plant (profile, location, calibration) stored on the server."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from terra.config import load_config
from terra.locations import get_location

from app.db.models import UserRow
from app.schemas.api import AuthIn, AuthOut, CalibrationIn, PlantIn, PlantStored, UserOut
from app.services import auth
from app.services import locations as loc_svc

router = APIRouter(tags=["account"])
CurrentUser = Annotated[UserRow, Depends(auth.current_user)]
OptionalUser = Annotated[UserRow | None, Depends(auth.optional_user)]
MAX_CSV_BYTES = 6_000_000


@router.post("/auth/signup", response_model=AuthOut)
def signup(body: AuthIn) -> dict:
    return auth.signup(body.email, body.password, body.name)


@router.post("/auth/login", response_model=AuthOut)
def login(body: AuthIn) -> dict:
    return auth.login(body.email, body.password)


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    auth.logout(authorization)
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser) -> dict:
    return auth.user_out(user)


@router.delete("/auth/me")
def delete_me(user: CurrentUser) -> dict:
    """Delete the account, its sessions and its stored plant."""
    auth.delete_account(user)
    return {"ok": True}


@router.get("/me/plant", response_model=PlantStored)
def get_plant(user: CurrentUser) -> dict:
    return auth.get_plant(user) or {}


@router.put("/me/plant", response_model=PlantStored)
def put_plant(body: PlantIn, user: CurrentUser) -> dict:
    if body.values is not None:
        chk = loc_svc.check_profile(body.values, body.site_id)
        if chk.errors:
            raise HTTPException(422, "; ".join(f"{k}: {v}" for k, v in chk.errors.items()))
    if body.site_id is not None and get_location(body.site_id) is None:
        raise HTTPException(422, "Unknown site.")
    return auth.save_plant(user, values=body.values, site_id=body.site_id, live_home=body.live_home,
                           calibration=body.calibration)


@router.post("/calibration")
async def calibration(body: CalibrationIn, user: OptionalUser) -> dict:
    """Calibrate the physics model to uploaded measured history. Signed-in users also get the result saved."""
    from terra.profile import apply_profile
    from terra.real.measured import UploadError, run

    if len(body.csv.encode()) > MAX_CSV_BYTES:
        raise HTTPException(413, "The file is larger than 6 MB. Upload up to one year of 15-minute or hourly data.")
    chk = loc_svc.check_profile(body.values, body.location_id)
    if chk.errors:
        raise HTTPException(422, "; ".join(f"{k}: {v}" for k, v in chk.errors.items()))
    loc = get_location(body.location_id or chk.clean.get("location_id") or loc_svc._home())
    applied = apply_profile(load_config(), loc, {k: v for k, v in chk.clean.items() if k != "location_id"})
    try:
        report = await run_in_threadpool(run, body.csv, applied.user_cfg, body.timezone, body.stamp, body.unit)
    except UploadError as exc:
        raise HTTPException(422, str(exc)) from exc
    report["location_id"] = loc.id
    if user is not None:
        auth.save_plant(user, calibration=report)
        report["saved_to_account"] = True
    return report
