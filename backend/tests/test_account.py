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
