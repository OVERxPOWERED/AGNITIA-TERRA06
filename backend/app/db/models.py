"""SQLite tables (SQLModel). Forecast numbers stay in Parquet run folders; the DB indexes runs and alerts."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.settings import get_settings

_engine = None


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


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().db_url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(_engine)
    return _engine


def record_run(name: str, meta: dict, alerts: list[dict]) -> None:
    with Session(engine()) as s:
        s.merge(RunRow(name=name, issue_time_utc=meta["issue_time_utc"], mode=meta["mode"],
                       n_alerts=len(alerts)))
        for a in alerts:
            existing = s.get(AlertRow, a["id"])
            row = AlertRow(**a, acknowledged=existing.acknowledged if existing else False)
            s.merge(row)
        s.commit()


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
