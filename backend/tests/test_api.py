"""API smoke tests. Require artifacts from `terra train`, `terra evaluate` and `terra forecast --mode replay`
(or set TERRA_ARTIFACTS_DIR to a folder that has them). Scheduler is disabled in tests."""
from __future__ import annotations

import os

import pytest

os.environ["TERRA_SCHEDULER_ENABLED"] = "false"
os.environ.setdefault("TERRA_DB_URL", "sqlite:///./test_terra.db")

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] in ("ok", "no_run_yet")


@pytest.mark.parametrize("path", ["/site", "/forecast?source=hybrid", "/forecast?source=solar&horizon=24",
                                  "/forecast/history?source=wind", "/models/compare?source=solar",
                                  "/models/compare?source=wind&by=lead_bucket", "/alerts", "/dispatch",
                                  "/dsm/summary", "/impact", "/assumptions", "/trust"])
def test_get_routes(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text


def test_forecast_shape(client):
    j = client.get("/forecast?source=hybrid").json()
    assert len(j["points"]) == 48
    p = j["points"][0]
    assert p["q05"] <= p["q10"] <= p["q50"] <= p["q90"] <= p["q95"]


def test_whatif(client):
    r = client.post("/whatif", json={"irradiance_scale": 0.6, "battery_mwh": 80})
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"before", "after"}


def test_whatif_validation(client):
    assert client.post("/whatif", json={"irradiance_scale": 9}).status_code == 422


def test_schedule_csv(client):
    r = client.get("/dsm/schedule.csv?source=hybrid")
    assert r.status_code == 200 and r.text.startswith("block_no")
