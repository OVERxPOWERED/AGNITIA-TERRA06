"""Optional accounts: signup, login, sessions, the stored plant, and password hashing."""
from __future__ import annotations

import os
import uuid

os.environ["TERRA_SCHEDULER_ENABLED"] = "false"
os.environ.setdefault("TERRA_DB_URL", "sqlite:///./test_terra.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import hash_password, verify_password


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _email() -> str:
    return f"t{uuid.uuid4().hex[:8]}@example.com"


def test_password_hash_roundtrip():
    h = hash_password("correct horse")
    assert h.startswith("scrypt$") and verify_password("correct horse", h) and not verify_password("wrong", h)


def test_signup_login_me_logout(client):
    e = _email()
    r = client.post("/auth/signup", json={"email": e, "password": "secret123", "name": "Asha"})
    assert r.status_code == 200 and r.json()["user"]["email"] == e
    assert client.post("/auth/signup", json={"email": e, "password": "secret123"}).status_code == 409
    assert client.post("/auth/login", json={"email": e, "password": "nope-nope"}).status_code == 401
    tok = client.post("/auth/login", json={"email": e.upper(), "password": "secret123"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/auth/me", headers=h).json()["name"] == "Asha"
    client.post("/auth/logout", headers=h)
    assert client.get("/auth/me", headers=h).status_code == 401


def test_validation_and_rate_limit(client):
    assert client.post("/auth/signup", json={"email": "bad", "password": "secret123"}).status_code == 422
    assert client.post("/auth/signup", json={"email": _email(), "password": "short"}).status_code == 422
    e = _email()
    client.post("/auth/signup", json={"email": e, "password": "secret123"})
    codes = [client.post("/auth/login", json={"email": e, "password": "wrong-pass"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_plant_is_stored_per_user(client):
    tok = client.post("/auth/signup", json={"email": _email(), "password": "secret123"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/me/plant", headers=h).json()["version"] == 0
    r = client.put("/me/plant", headers=h, json={"values": {"solar_ac_mw": 55, "tracking": "single_axis"}, "site_id": "bhadla"})
    assert r.status_code == 200 and r.json()["values"]["solar_ac_mw"] == 55 and r.json()["site_id"] == "bhadla"
    assert client.put("/me/plant", headers=h, json={"values": {"solar_ac_mw": -1}}).status_code == 422
    other = client.post("/auth/signup", json={"email": _email(), "password": "secret123"}).json()["token"]
    assert client.get("/me/plant", headers={"Authorization": f"Bearer {other}"}).json()["values"] == {}
    assert client.get("/me/plant").status_code == 401
    assert client.delete("/auth/me", headers=h).json()["ok"] is True
    assert client.get("/auth/me", headers=h).status_code == 401


def test_calibration_rejects_bad_files(client):
    r = client.post("/calibration", json={"csv": "a,b\n1,2\n"})
    assert r.status_code == 422 and "timestamp" in r.json()["detail"].lower()


def test_whatsapp_and_schedule_endpoints(client):
    tok = client.post("/auth/signup", json={"email": _email(), "password": "secret123"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    st = client.get("/notify/status").json()
    assert st["provider"] in ("none", "meta", "twilio")
    assert client.post("/me/notify/test", headers=h).status_code == 422          # no number yet
    bad = client.put("/me/plant", headers=h, json={"values": {"whatsapp_alerts": "critical", "whatsapp_number": "98765"}})
    assert bad.status_code == 422
    ok = client.put("/me/plant", headers=h, json={"values": {"whatsapp_alerts": "critical", "whatsapp_number": "+91 98765 43210"}})
    assert ok.status_code == 200 and ok.json()["values"]["whatsapp_number"] == "+919876543210"
    r = client.post("/me/notify/test", headers=h).json()
    assert r["status"] in ("logged", "sent", "failed")
    assert client.get("/me/notifications", headers=h).json()[0]["to"] == "+919876543210"
    blocks = [[f"2026-10-10T{h_:02d}:{m:02d}:00Z", 10.0] for h_ in range(24) for m in (0, 15, 30, 45)][:96]
    first = client.put("/me/schedule", headers=h, json={"date": "2026-10-10", "blocks": blocks}).json()
    again = client.put("/me/schedule", headers=h, json={"date": "2026-10-10", "blocks": blocks}).json()
    assert first["revision"] == 0 and again["revision"] == 1 and len(again["blocks"]) == 96
    assert client.get("/me/schedule?date=2026-10-10", headers=h).json()["revision"] == 1


def test_internal_monitor_needs_token(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.settings import get_settings
    monkeypatch.setenv("TERRA_MONITOR_TOKEN", "s3cret")
    get_settings.cache_clear()
    try:
        c = TestClient(create_app())
        assert c.post("/internal/monitor").status_code == 404
        assert c.post("/internal/monitor", headers={"X-Monitor-Token": "nope"}).status_code == 404
        r = c.post("/internal/monitor", headers={"X-Monitor-Token": "s3cret"})
        assert r.status_code == 200 and "plants" in r.json()
    finally:
        get_settings.cache_clear()
