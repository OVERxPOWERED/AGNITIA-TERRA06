"""WhatsApp alerts: provider adapters (Meta WhatsApp Cloud API, Twilio), the plant monitor and the send log.

Provider choice and credentials come from environment variables (TERRA_WHATSAPP_PROVIDER, TERRA_META_WA_*,
TERRA_TWILIO_*). With provider "none" messages are only logged, so the whole flow can be tested without an account.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from sqlmodel import Session, select
from terra.engines.deviation_watch import deviation_risk_alerts
from terra.logs import get_logger

from app.db.models import NotificationRow, PlantRow, ScheduleRow, UserRow, engine
from app.settings import get_settings

log = get_logger(__name__)
TIMEOUT_S = 20


def provider_status() -> dict:
    s = get_settings()
    p = s.whatsapp_provider.lower()
    ready = {"meta": bool(s.meta_wa_token and s.meta_wa_phone_id), "twilio": bool(s.twilio_sid and s.twilio_token)}.get(p, False)
    return {"provider": p, "ready": ready, "template": s.meta_wa_template or None if p == "meta" else None,
            "from": s.twilio_whatsapp_from if p == "twilio" else None, "content_template": bool(s.twilio_content_sid),
            "monitor_minutes": s.monitor_minutes if s.monitor_enabled else None}


def send_whatsapp(to: str, text: str, params: list[str]) -> tuple[str, str]:
    """Returns (status, detail). status: sent | failed | logged."""
    s = get_settings()
    p = s.whatsapp_provider.lower()
    try:
        if p == "meta" and s.meta_wa_token and s.meta_wa_phone_id:
            url = f"https://graph.facebook.com/v21.0/{s.meta_wa_phone_id}/messages"
            if s.meta_wa_template:
                body = {"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "template",
                        "template": {"name": s.meta_wa_template, "language": {"code": s.meta_wa_template_lang},
                                     "components": [{"type": "body", "parameters": [{"type": "text", "text": x[:900]} for x in params]}]}}
            else:
                body = {"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "text", "text": {"body": text[:4000]}}
            r = requests.post(url, json=body, headers={"Authorization": f"Bearer {s.meta_wa_token}"}, timeout=TIMEOUT_S)
            if r.ok:
                return "sent", r.json().get("messages", [{}])[0].get("id", "")
            return "failed", f"HTTP {r.status_code}: {r.text[:300]}"
        if p == "twilio" and s.twilio_sid and s.twilio_token:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_sid}/Messages.json"
            base = {"From": s.twilio_whatsapp_from, "To": f"whatsapp:{to}"}
            auth = (s.twilio_sid, s.twilio_token)
            # Content templates when one is configured (senders that refuse free text, or outside the 24 h window);
            # otherwise plain text, which Twilio only delivers inside the 24 h window after the user last wrote.
            if s.twilio_content_sid:
                body = {**base, "ContentSid": s.twilio_content_sid,
                        "ContentVariables": json.dumps({"1": f"{params[0]}: {params[1]}"[:900], "2": params[2][:200]})}
                r = requests.post(url, data=body, auth=auth, timeout=TIMEOUT_S)
                if r.ok:
                    return "sent", r.json().get("sid", "")
                log.warning("Twilio template send failed (%s); trying plain text", r.status_code)
            r = requests.post(url, data={**base, "Body": text[:1500]}, auth=auth, timeout=TIMEOUT_S)
            if r.ok:
                return "sent", r.json().get("sid", "")
            return "failed", f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:  # noqa: BLE001
        return "failed", f"{type(exc).__name__}: {exc}"
    log.info("WhatsApp (not configured, logged only) to %s: %s", to, text)
    return "logged", "No WhatsApp provider is configured on the server; the message was only logged."


def _ist(iso: str) -> str:
    return pd.Timestamp(iso).tz_convert("Asia/Kolkata").strftime("%d %b %H:%M")


def format_alert(plant: str, a: dict) -> tuple[str, list[str]]:
    window = f"{_ist(a['start_utc'])} to {_ist(a['end_utc'])} IST"
    url = get_settings().public_url.rstrip("/") + "/alerts"
    text = f"Vidyut CRITICAL alert for {plant}\n{a['message']}\nWhen: {window}\nOpen: {url}"
    return text, [plant, a["message"], window]


def record(user_id: str, key: str, to: str, status: str, detail: str, message: str) -> None:
    with Session(engine()) as s:
        s.add(NotificationRow(id=uuid.uuid4().hex, user_id=user_id, alert_key=key, to=to, status=status,
                              detail=detail[:500], message=message[:2000]))
        s.commit()


def already_sent(user_id: str, key: str, hours: int = 24) -> bool:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    with Session(engine()) as s:
        rows = s.exec(select(NotificationRow).where(NotificationRow.user_id == user_id, NotificationRow.alert_key == key)).all()
        return any((r.sent_at if r.sent_at.tzinfo else r.sent_at.replace(tzinfo=timezone.utc)) > since
                   and r.status in ("sent", "logged") for r in rows)


def sent_today(user_id: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    with Session(engine()) as s:
        rows = s.exec(select(NotificationRow).where(NotificationRow.user_id == user_id)).all()
        return sum(1 for r in rows if r.status == "sent" and (r.sent_at if r.sent_at.tzinfo else r.sent_at.replace(tzinfo=timezone.utc)) > since)


def recent(user_id: str, limit: int = 20) -> list[dict]:
    with Session(engine()) as s:
        rows = s.exec(select(NotificationRow).where(NotificationRow.user_id == user_id)
                      .order_by(NotificationRow.sent_at.desc()).limit(limit)).all()
        return [{"sent_at": (r.sent_at if r.sent_at.tzinfo else r.sent_at.replace(tzinfo=timezone.utc)).isoformat(),
                 "status": r.status, "detail": r.detail, "message": r.message, "to": r.to} for r in rows]


# ---------- submitted schedules ----------
def get_schedule(user_id: str, date: str, source: str = "hybrid") -> dict | None:
    with Session(engine()) as s:
        r = s.get(ScheduleRow, f"{user_id}|{date}|{source}")
        if not r:
            return None
        return {"date": r.date, "source": r.source, "revision": r.revision, "blocks": json.loads(r.blocks_json),
                "submitted_at": (r.submitted_at if r.submitted_at.tzinfo else r.submitted_at.replace(tzinfo=timezone.utc)).isoformat()}


def put_schedule(user_id: str, date: str, blocks: list[list], source: str = "hybrid") -> dict:
    with Session(engine()) as s:
        rid = f"{user_id}|{date}|{source}"
        r = s.get(ScheduleRow, rid)
        if r:
            r.blocks_json, r.revision, r.submitted_at = json.dumps(blocks), r.revision + 1, datetime.now(timezone.utc)
        else:
            r = ScheduleRow(id=rid, user_id=user_id, date=date, source=source, blocks_json=json.dumps(blocks))
        s.add(r)
        s.commit()
    return get_schedule(user_id, date, source)


def committed_series(user_id: str, issue: pd.Timestamp) -> pd.Series | None:
    """Submitted hybrid blocks for today and the next two IST days, as one series (block end UTC -> MW)."""
    day0 = issue.tz_convert("Asia/Kolkata").normalize()
    parts = []
    for d in range(3):
        sc = get_schedule(user_id, (day0 + pd.Timedelta(days=d)).strftime("%Y-%m-%d"))
        if sc:
            parts.append(pd.Series({pd.Timestamp(t): float(v) for t, v in sc["blocks"]}))
    return pd.concat(parts).sort_index() if parts else None


def deviation_alerts_for_run(user_id: str, run_dir, avc_mw: float, plant: str) -> list[dict]:
    p = run_dir / "blocks_p50.parquet"
    if not p.exists():
        return []
    b = pd.read_parquet(p)
    expected = pd.Series(b["hybrid"].to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(b["block_end_utc"], utc=True)))
    issue = pd.Timestamp(json.loads((run_dir / "run.json").read_text())["issue_time_utc"])
    committed = committed_series(user_id, issue)
    if committed is None:
        return []
    return [a.to_dict() for a in deviation_risk_alerts(expected, committed, avc_mw, issue, plant=plant)]


# ---------- monitor ----------
def monitor_once(only_user: str | None = None) -> dict:
    """Run a live forecast for every signed-in plant with WhatsApp alerts on and send new critical alerts."""
    from terra.config import load_config
    from terra.locations import get_location
    from terra.pipelines.forecast import run_forecast
    from terra.profile import apply_profile

    from app.services import locations as loc_svc

    s = get_settings()
    done = {"plants": 0, "sent": 0, "logged": 0, "failed": 0}
    with Session(engine()) as ses:
        plants = ses.exec(select(PlantRow)).all()
        users = {u.id: u for u in ses.exec(select(UserRow)).all()}
    for p in plants:
        values = json.loads(p.values_json or "{}")
        if only_user and p.user_id != only_user:
            continue
        if values.get("whatsapp_alerts") != "critical" or not values.get("whatsapp_number") or p.user_id not in users:
            continue
        try:
            chk = loc_svc.check_profile(values, p.site_id)
            if chk.errors:
                continue
            loc = get_location(p.site_id or loc_svc._home())
            cal = json.loads(p.calibration_json or "{}").get("factors", {})
            clean = {k: v for k, v in chk.clean.items() if k != "location_id"}
            applied = apply_profile(load_config(), loc, clean, cal)
            out = run_forecast(applied.user_cfg, "live", runs_dir=loc_svc.ROOT / loc.id / f"monitor-{p.user_id[:8]}",
                               write_latest=False, model_cfg=applied.model_cfg, adjust=applied, site_id=loc.id)
            alerts = json.loads((out / "alerts.json").read_text())
            hyb_cap = applied.summary["solar_ac_mw"] + applied.summary["wind_mw"]
            alerts += deviation_alerts_for_run(p.user_id, out, hyb_cap, applied.summary["plant_name"])
            done["plants"] += 1
            for a in alerts:
                if a["severity"] != "critical" and a["type"] != "DEVIATION_RISK":
                    continue
                key = f"{a['type']}|{a['source']}|{a['start_utc']}"
                if already_sent(p.user_id, key) or sent_today(p.user_id) >= s.max_whatsapp_per_day:
                    continue
                text, params = format_alert(applied.summary["plant_name"], a)
                status, detail = send_whatsapp(values["whatsapp_number"], text, params)
                record(p.user_id, key, values["whatsapp_number"], status, detail, text)
                done[status] = done.get(status, 0) + 1
        except Exception:
            log.exception("monitor failed for plant of user %s", p.user_id)
    log.info("monitor run: %s", done)
    return done
