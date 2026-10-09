"""Tests for Postgres URL normalization, startup DB re-seed, and unreachable DB fallback."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.models import (
    AlertRow,
    RunRow,
    engine,
    normalize_db_url,
    reseed_if_empty,
    reset_engine,
)
from app.main import app
from app.settings import get_settings


def test_normalize_db_url():
    # Neon postgres:// with sslmode
    neon_url = "postgres://user:pass@ep-demo.neon.tech/neondb?sslmode=require"
    assert normalize_db_url(neon_url) == "postgresql+psycopg://user:pass@ep-demo.neon.tech/neondb?sslmode=require"

    # Standard postgresql://
    pg_url = "postgresql://user:pass@ep-demo.neon.tech/neondb?sslmode=require"
    assert normalize_db_url(pg_url) == "postgresql+psycopg://user:pass@ep-demo.neon.tech/neondb?sslmode=require"

    # Already normalized
    norm_url = "postgresql+psycopg://user:pass@localhost:5432/db?sslmode=require"
    assert normalize_db_url(norm_url) == norm_url

    # SQLite
    sqlite_url = "sqlite:///./terra.db"
    assert normalize_db_url(sqlite_url) == sqlite_url


def test_idempotent_reseed_on_empty_db(monkeypatch, tmp_path):
    db_file = tmp_path / "test_reseed.db"
    test_db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("TERRA_DB_URL", test_db_url)
    get_settings.cache_clear()
    reset_engine()

    try:
        eng = engine()
        with Session(eng) as s:
            runs_count = len(list(s.exec(select(RunRow))))
            assert runs_count == 0

        # First re-seed on empty DB
        reseeded = reseed_if_empty()
        assert reseeded is True

        with Session(eng) as s:
            runs_after = list(s.exec(select(RunRow)))
            alerts_after = list(s.exec(select(AlertRow)))
            assert len(runs_after) >= 1
            first_run_name = runs_after[0].name
            assert len(alerts_after) >= 0

        # Second re-seed must be idempotent (returns False, does not duplicate)
        reseeded_second = reseed_if_empty()
        assert reseeded_second is False

        with Session(eng) as s:
            runs_second = list(s.exec(select(RunRow)))
            assert len(runs_second) == len(runs_after)
            assert runs_second[0].name == first_run_name
    finally:
        reset_engine()
        get_settings.cache_clear()


def test_unreachable_postgres_fallback(monkeypatch):
    """When configured Postgres is unreachable, API must degrade gracefully to SQLite and serve forecasts."""
    unreachable_url = "postgresql://invalid_user:invalid_pass@127.0.0.1:54321/neondb?connect_timeout=1"
    monkeypatch.setenv("TERRA_DB_URL", unreachable_url)
    get_settings.cache_clear()
    reset_engine()

    try:
        with TestClient(app) as client:
            # /health must not depend on the DB and return 200
            r_health = client.get("/health")
            assert r_health.status_code == 200
            assert r_health.json()["status"] in ("ok", "no_run_yet")

            # /forecast must still return 200
            r_forecast = client.get("/forecast?source=hybrid")
            assert r_forecast.status_code == 200
            assert len(r_forecast.json()["points"]) == 48

            # /alerts must degrade to fallback SQLite rather than crashing
            r_alerts = client.get("/alerts")
            assert r_alerts.status_code == 200
    finally:
        reset_engine()
        get_settings.cache_clear()
