"""Database models and connections (SQLModel).

Supports SQLite (default) and Postgres (via psycopg3).
Gracefully degrades to local SQLite if configured Postgres is unreachable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, text
from sqlmodel import Field, Session, SQLModel, create_engine, select
from terra.paths import ARTIFACTS

from app.settings import get_settings

log = logging.getLogger(__name__)

_engine: Engine | None = None


class RunRow(SQLModel, table=True):
    name: str = Field(primary_key=True)          # folder name, e.g. 20260410T00
    issue_time_utc: str
    mode: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    n_alerts: int = 0


class AlertRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    type: str
    source: str
    start_utc: str
    end_utc: str
    severity: str
    probability: float
    magnitude_mw: float
    message: str
    issue_time_utc: str
    acknowledged: bool = False


def normalize_db_url(raw_url: str) -> str:
    """Normalize postgres:// and postgresql:// to postgresql+psycopg:// preserving query params."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _create_engine_for_url(norm_url: str, default_connect_timeout: int = 5) -> Engine:
    if norm_url.startswith("sqlite"):
        return create_engine(norm_url, connect_args={"check_same_thread": False})

    # Postgres / psycopg
    connect_args: dict[str, Any] = {}
    if "connect_timeout" not in norm_url:
        connect_args["connect_timeout"] = default_connect_timeout

    return create_engine(
        norm_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )


def reset_engine() -> None:
    """Reset global engine (used in tests)."""
    global _engine
    _engine = None


def engine() -> Engine:
    """Get or initialize the database engine with graceful fallback."""
    global _engine
    if _engine is not None:
        return _engine

    raw_url = get_settings().db_url
    norm_url = normalize_db_url(raw_url)

    if norm_url.startswith("sqlite"):
        _engine = _create_engine_for_url(norm_url)
        SQLModel.metadata.create_all(_engine)
        return _engine

    # Postgres: attempt connection, fallback to SQLite if unreachable
    try:
        eng = _create_engine_for_url(norm_url)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        SQLModel.metadata.create_all(eng)
        _engine = eng
        log.info("Database connected successfully.")
        return _engine
    except Exception as exc:  # noqa: BLE001
        masked = norm_url.split("@")[-1] if "@" in norm_url else norm_url
        log.warning(
            "Configured database (%s) is unreachable (%s); gracefully falling back to local SQLite",
            masked,
            exc,
        )
        fallback_path = ARTIFACTS / "terra_fallback.db"
        try:
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_url = f"sqlite:///{fallback_path}"
            _engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
            SQLModel.metadata.create_all(_engine)
        except Exception:  # noqa: BLE001
            _engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
            SQLModel.metadata.create_all(_engine)
        return _engine


def ping() -> dict[str, Any]:
    """Cheap DB round-trip for keep-warm pingers (never raises). Neon free tier suspends compute after
    ~5 idle minutes; any query resets that timer."""
    import time
    t0 = time.perf_counter()
    try:
        with engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"db": "unavailable", "error": type(exc).__name__,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def record_run(name: str, meta: dict, alerts: list[dict]) -> None:
    """Persist run metadata and alerts into the database (idempotent)."""
    with Session(engine()) as s:
        s.merge(RunRow(name=name, issue_time_utc=meta["issue_time_utc"], mode=meta["mode"],
                       n_alerts=len(alerts)))
        for a in alerts:
            existing = s.get(AlertRow, a["id"])
            row = AlertRow(**a, acknowledged=existing.acknowledged if existing else False)
            s.merge(row)
        s.commit()


def reseed_if_empty() -> bool:
    """If DB runs table is empty (fresh or reset DB), ingest latest run from artifacts.

    Idempotent: returns True if reseeded, False if DB already populated or no artifacts yet.
    """
    with Session(engine()) as s:
        has_runs = s.exec(select(RunRow).limit(1)).first() is not None
        if has_runs:
            return False

    try:
        from app.services import runs
        latest_data = runs.latest()
        record_run(latest_data["name"], latest_data["meta"], latest_data["alerts"])
        log.info("Re-seeded empty database from latest run: %s", latest_data["name"])
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("Database re-seed skipped: %s", exc)
        return False


def list_alerts(active_after: str | None = None, limit: int = 200) -> list[AlertRow]:
    with Session(engine()) as s:
        q = select(AlertRow)
        if active_after:
            q = q.where(AlertRow.end_utc >= active_after)
        return list(s.exec(q.order_by(AlertRow.start_utc).limit(limit)))


def acknowledge(alert_id: str) -> bool:
    with Session(engine()) as s:
        row = s.get(AlertRow, alert_id)
        if not row:
            return False
        row.acknowledged = True
        s.add(row)
        s.commit()
        return True


# ---------- accounts (optional login) ----------
class UserRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str = ""
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionRow(SQLModel, table=True):
    token_hash: str = Field(primary_key=True)        # sha256 of the bearer token; the token itself is never stored
    user_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime


class PlantRow(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    site_id: str | None = None
    live_home: bool = False
    values_json: str = "{}"                           # plant profile (validated by terra.profile)
    calibration_json: str = "{}"                      # factors + report from the measured-history upload
    version: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
