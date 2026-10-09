"""/locations: allowlist, unknown ids, and the job lifecycle with the heavy pipeline stubbed out."""
from __future__ import annotations

import os
import time

os.environ["TERRA_SCHEDULER_ENABLED"] = "false"
os.environ.setdefault("TERRA_DB_URL", "sqlite:///./test_terra.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import locations as svc


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_allowlist_has_a_home_site(client):
    rows = client.get("/locations").json()
    assert len(rows) >= 2 and sum(r["is_home"] for r in rows) == 1


def test_unknown_location_is_rejected(client):
    assert client.post("/locations/atlantis/forecast").status_code == 404
    assert client.get("/locations/jobs/nope").status_code == 404


def test_job_lifecycle_and_reuse(client, monkeypatch):
    calls = []

    def fake_run(job):
        calls.append(job["loc"])
        job["status"] = "running"
        for s in ("weather", "models", "plan"):
            job["step"] = s
        job.update(status="failed", error="stub", finished=svc._now())

    monkeypatch.setattr(svc, "_run", fake_run)
    svc._jobs.clear()
    j = client.post("/locations/bhadla/forecast").json()
    for _ in range(50):
        s = client.get(f"/locations/jobs/{j['job_id']}").json()
        if s["status"] != "queued":
            break
        time.sleep(0.05)
    assert s["status"] == "failed" and s["error"] == "stub" and calls == ["bhadla"]


def test_profile_schema_and_validation(client):
    sch = client.get("/profile/schema").json()
    keys = {f["key"] for f in sch["fields"]}
    assert {"solar_ac_mw", "wind_turbines", "battery_energy_mwh", "demand_peak_mw"} <= keys
    ok = client.post("/profile/check", json={"values": {"solar_ac_mw": 60, "wind_turbines": 30}}).json()
    assert ok["errors"] == {} and ok["summary"]["solar_scale"] == 1.5 and ok["summary"]["wind_scale"] == 1.2
    bad = client.post("/profile/check", json={"values": {"solar_ac_mw": -5, "soc_min_frac": 0.95, "location_id": "mars"}}).json()
    assert {"solar_ac_mw", "soc_min_frac", "location_id"} <= set(bad["errors"])
    assert client.post("/locations/bhadla/forecast", json={"values": {"solar_ac_mw": -5}}).status_code == 422
