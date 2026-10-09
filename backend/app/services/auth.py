"""Optional accounts: email + password, opaque bearer tokens, and a server-side copy of the user's plant.

Passwords are hashed with scrypt (stdlib); tokens are random, stored only as SHA-256 hashes, and expire after
TOKEN_DAYS. Login failures are rate-limited per email in memory.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException
from sqlmodel import Session, select

from app.db.models import PlantRow, SessionRow, UserRow, engine

TOKEN_DAYS = 30
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failures: dict[str, list[float]] = defaultdict(list)
MAX_FAILURES, WINDOW_S = 5, 600


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, dklen=32, **SCRYPT)
    return "scrypt${n}${r}${p}${s}${h}".format(**SCRYPT, s=base64.b64encode(salt).decode(), h=base64.b64encode(dk).decode())


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, s, h = stored.split("$")
        dk = hashlib.scrypt(pw.encode(), salt=base64.b64decode(s), dklen=32, n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(dk, base64.b64decode(h))
    except Exception:  # noqa: BLE001
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _issue(s: Session, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    s.add(SessionRow(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user_id,
                     expires_at=_now() + timedelta(days=TOKEN_DAYS)))
    return token


def user_out(u: UserRow) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "created_at": _aware(u.created_at).isoformat()}


def signup(email: str, password: str, name: str) -> dict:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(422, "Use a password of at least 8 characters.")
    with Session(engine()) as s:
        if s.exec(select(UserRow).where(UserRow.email == email)).first():
            raise HTTPException(409, "An account with this email already exists. Sign in instead.")
        u = UserRow(id=uuid.uuid4().hex, email=email, name=name.strip()[:80], password_hash=hash_password(password))
        s.add(u)
        token = _issue(s, u.id)
        s.commit()
        s.refresh(u)
        return {"token": token, "user": user_out(u)}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    now = time.time()
    _failures[email] = [t for t in _failures[email] if now - t < WINDOW_S]
    if len(_failures[email]) >= MAX_FAILURES:
        raise HTTPException(429, "Too many attempts. Wait ten minutes and try again.")
    with Session(engine()) as s:
        u = s.exec(select(UserRow).where(UserRow.email == email)).first()
        if not u or not verify_password(password, u.password_hash):
            _failures[email].append(now)
            raise HTTPException(401, "Email or password is incorrect.")
        _failures.pop(email, None)
        token = _issue(s, u.id)
        s.commit()
        return {"token": token, "user": user_out(u)}


def _session(token: str) -> tuple[UserRow, SessionRow] | None:
    h = hashlib.sha256(token.encode()).hexdigest()
    with Session(engine()) as s:
        row = s.get(SessionRow, h)
        if not row or _aware(row.expires_at) < _now():
            return None
        u = s.get(UserRow, row.user_id)
        return (u, row) if u else None


def current_user(authorization: str | None = Header(default=None)) -> UserRow:
    """FastAPI dependency: the signed-in user, or 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in to use this.")
    found = _session(authorization[7:].strip())
    if not found:
        raise HTTPException(401, "Your session has expired. Sign in again.")
    return found[0]


def optional_user(authorization: str | None = Header(default=None)) -> UserRow | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    found = _session(authorization[7:].strip())
    return found[0] if found else None


def logout(authorization: str | None) -> None:
    if authorization and authorization.lower().startswith("bearer "):
        h = hashlib.sha256(authorization[7:].strip().encode()).hexdigest()
        with Session(engine()) as s:
            row = s.get(SessionRow, h)
            if row:
                s.delete(row)
                s.commit()


def delete_account(user: UserRow) -> None:
    with Session(engine()) as s:
        for r in s.exec(select(SessionRow).where(SessionRow.user_id == user.id)):
            s.delete(r)
        p = s.get(PlantRow, user.id)
        if p:
            s.delete(p)
        u = s.get(UserRow, user.id)
        if u:
            s.delete(u)
        s.commit()


def get_plant(user: UserRow) -> dict | None:
    with Session(engine()) as s:
        p = s.get(PlantRow, user.id)
        if not p:
            return None
        return {"site_id": p.site_id, "live_home": p.live_home, "values": json.loads(p.values_json),
                "calibration": json.loads(p.calibration_json), "version": p.version,
                "updated_at": _aware(p.updated_at).isoformat()}


def save_plant(user: UserRow, *, values: dict | None = None, site_id: str | None = None, live_home: bool | None = None,
               calibration: dict | None = None) -> dict:
    with Session(engine()) as s:
        p = s.get(PlantRow, user.id) or PlantRow(user_id=user.id)
        if values is not None:
            p.values_json = json.dumps(values)
        if site_id is not None:
            p.site_id = site_id
        if live_home is not None:
            p.live_home = live_home
        if calibration is not None:
            p.calibration_json = json.dumps(calibration)
        p.version += 1
        p.updated_at = _now()
        s.add(p)
        s.commit()
    return get_plant(user)
