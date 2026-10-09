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


def test_health_accepts_head(client):
    assert client.head("/health").status_code == 200


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


def test_models_compare_daylight(client):
    # Solar all-hours vs daylight-only
    r_all = client.get("/models/compare?source=solar")
    assert r_all.status_code == 200
    j_all = r_all.json()
    assert j_all["daylight_only"] is False

    r_day = client.get("/models/compare?source=solar&daylight=true")
    assert r_day.status_code == 200
    j_day = r_day.json()
    assert j_day["daylight_only"] is True

    ens_all = next(row for row in j_all["rows"] if row["model"] == "ensemble")
    ens_day = next(row for row in j_day["rows"] if row["model"] == "ensemble")
    assert ens_day["picp80"] < ens_all["picp80"]

    # Wind with daylight=true returns same as all hours, daylight_only is False
    r_wind = client.get("/models/compare?source=wind&daylight=true")
    assert r_wind.status_code == 200
    j_wind = r_wind.json()
    assert j_wind["daylight_only"] is False



def test_schedule_csv_forces_download(client):
    r = client.get("/dsm/schedule.csv?source=hybrid")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="terra_schedule_hybrid.csv"' in r.headers["content-disposition"]
    assert len(r.text.strip().splitlines()) == 97          # header + 96 blocks


def test_health_deep_reports_db(client):
    for r in (client.get("/health/deep"), client.head("/health/deep")):
        assert r.status_code == 200
    body = client.get("/health/deep").json()
    assert body["status"] == "ok" and body["db"] == "ok" and body["latency_ms"] >= 0


def test_alerts_fall_back_to_run_file_when_db_down(client, monkeypatch):
    from app.db import models as db

    def boom(*a, **k):
        raise RuntimeError("neon suspended")
    monkeypatch.setattr(db, "list_alerts", boom)
    r = client.get("/alerts")
    assert r.status_code == 200
    assert all(a["acknowledged"] is False for a in r.json())


def test_ack_returns_503_when_db_down(client, monkeypatch):
    from app.db import models as db

    def boom(*a, **k):
        raise RuntimeError("neon suspended")
    monkeypatch.setattr(db, "acknowledge", boom)
    assert client.post("/alerts/whatever/ack").status_code == 503
