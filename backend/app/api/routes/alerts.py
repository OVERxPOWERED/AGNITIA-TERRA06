from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.db import models as db
from app.schemas.api import AlertOut
from app.services import runs

log = logging.getLogger(__name__)

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def alerts(active_after: str | None = None) -> list[AlertOut]:
    try:
        return [AlertOut(**a.model_dump()) for a in db.list_alerts(active_after)]
    except Exception as exc:  # noqa: BLE001  (e.g. Neon waking up / unreachable)
        log.warning("alerts: database unavailable (%s); serving alerts from the latest run file", type(exc).__name__)
        try:
            rows = runs.latest()["alerts"]
        except runs.NoRunYet:
            return []
        return [AlertOut(**{**a, "acknowledged": False}) for a in rows
                if not active_after or a["end_utc"] >= active_after]


@router.post("/alerts/{alert_id}/ack")
def ack(alert_id: str) -> dict:
    try:
        found = db.acknowledge(alert_id)
    except Exception as exc:
        log.warning("ack: database unavailable (%s)", type(exc).__name__)
        raise HTTPException(503, "database is waking up, please retry in a few seconds") from exc
    if not found:
        raise HTTPException(404, "alert not found")
    return {"ok": True}


@router.get("/alerts/stream")
async def stream(request: Request):
    """Server-Sent Events: 'run_complete' and 'alert' events pushed by the scheduler."""
    queue: asyncio.Queue = asyncio.Queue()
    request.app.state.subscribers.add(queue)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield {"event": event["type"], "data": json.dumps(event["data"])}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            request.app.state.subscribers.discard(queue)

    return EventSourceResponse(gen())
