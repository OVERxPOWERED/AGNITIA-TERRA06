"""Optional login and the signed-in user's plant (profile, location, calibration) stored on the server."""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from terra.config import load_config
from terra.locations import get_location

from app.db.models import UserRow
from app.schemas.api import AuthIn, AuthOut, CalibrationIn, PlantIn, PlantStored, SchedulePut, UserOut
from app.services import auth, notify
from app.services import locations as loc_svc

router = APIRouter(tags=["account"])
CurrentUser = Annotated[UserRow, Depends(auth.current_user)]
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
    values = body.values
    if values is not None:
        chk = loc_svc.check_profile(values, body.site_id)
        if chk.errors:
            raise HTTPException(422, "; ".join(f"{k}: {v}" for k, v in chk.errors.items()))
        values = chk.clean                                  # stored normalised (numbers, phone format)
    if body.site_id is not None and get_location(body.site_id) is None:
        raise HTTPException(422, "Unknown site.")
    return auth.save_plant(user, values=values, site_id=body.site_id, live_home=body.live_home,
                           calibration=body.calibration)


@router.post("/calibration")
async def calibration(body: CalibrationIn) -> dict:
    """Calibrate the physics model to uploaded measured history. Nothing is stored here: the client keeps the
    result and, when signed in, saves the adopted calibration with its plant (PUT /me/plant)."""
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
        report = await run_in_threadpool(run, body.csv, applied, body.timezone, body.stamp, body.unit)
    except UploadError as exc:
        raise HTTPException(422, str(exc)) from exc
    report["location_id"] = loc.id
    return report


# ---------- WhatsApp alerts and submitted schedules ----------
@router.get("/notify/status")
def notify_status() -> dict:
    """Which WhatsApp provider the server is configured with (no secrets)."""
    return notify.provider_status()


@router.post("/internal/monitor")
async def internal_monitor(x_monitor_token: str | None = Header(default=None)) -> dict:
    """Run the plant monitor for every signed-in plant. Called by an external cron (it also wakes a sleeping host)."""
    from app.settings import get_settings
    want = get_settings().monitor_token
    if not want or not x_monitor_token or not secrets.compare_digest(x_monitor_token, want):
        raise HTTPException(404, "Not found.")
    return await run_in_threadpool(notify.monitor_once)


@router.post("/me/notify/test")
def notify_test(user: CurrentUser) -> dict:
    p = auth.get_plant(user) or {}
    num = (p.get("values") or {}).get("whatsapp_number")
    if not num:
        raise HTTPException(422, "Add a WhatsApp number in Plant settings and save first.")
    name = (p.get("values") or {}).get("plant_name") or "your plant"
    text = f"Vidyut test message for {name}. Critical alerts for this plant will arrive on this number."
    status, detail = notify.send_whatsapp(num, text, [name, "Test message \u00b7 Vidyut \u00b7 now", "Alerts are set up for this number.", "Nothing to do; this is only a test.", "no window \u00b7 0.0 MW"])
    notify.record(user.id, f"TEST|{status}", num, status, detail, text)
    return {"status": status, "detail": detail}


@router.post("/me/notify/check")
async def notify_check(user: CurrentUser) -> dict:
    """Run the plant monitor now for this user (the server also runs it on a schedule)."""
    return await run_in_threadpool(notify.monitor_once, user.id)


@router.get("/me/notifications")
def notifications(user: CurrentUser) -> list[dict]:
    return notify.recent(user.id)


@router.get("/me/schedule")
def get_schedule(date: str, user: CurrentUser) -> dict:
    return notify.get_schedule(user.id, date) or {}


@router.put("/me/schedule")
def put_schedule(body: SchedulePut, user: CurrentUser) -> dict:
    """Record the schedule submitted to the load despatch centre (a re-submit counts as a revision)."""
    if not 1 <= len(body.blocks) <= 200:
        raise HTTPException(422, "A day has 96 blocks of 15 minutes.")
    return notify.put_schedule(user.id, body.date, body.blocks, body.source)
