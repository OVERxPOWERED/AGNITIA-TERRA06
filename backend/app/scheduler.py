"""Background job: produce a forecast run, index it in SQLite and notify SSE subscribers."""
from __future__ import annotations

import asyncio
import json

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from terra.config import load_config
from terra.logs import get_logger
from terra.pipelines.forecast import run_forecast

from app.db import models as db
from app.services import runs
from app.settings import get_settings

log = get_logger(__name__)


class ForecastJob:
    def __init__(self, app) -> None:
        self.app = app
        self.settings = get_settings()
        self.virtual_now = pd.Timestamp(self.settings.replay_start, tz="UTC")
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def tick(self) -> None:
        s = self.settings
        try:
            at = self.virtual_now.isoformat() if s.mode == "replay" else None
            out = run_forecast(load_config(), s.mode, at)
            meta = json.loads((out / "run.json").read_text())
            alerts = json.loads((out / "alerts.json").read_text())
            db.record_run(out.name, meta, alerts)
            runs.clear_cache()
            self.publish({"type": "run_complete", "data": {"run": out.name, "issue_time_utc": meta["issue_time_utc"]}})
            for a in alerts:
                self.publish({"type": "alert", "data": a})
            if s.mode == "replay":
                self.virtual_now += pd.Timedelta(hours=s.replay_step_hours)
        except Exception:
            log.exception("forecast job failed; serving last good run")

    def publish(self, event: dict) -> None:
        loop = getattr(self.app.state, "loop", None)
        for q in list(self.app.state.subscribers):
            if loop:
                loop.call_soon_threadsafe(q.put_nowait, event)

    def monitor(self) -> None:
        try:
            from app.services.notify import monitor_once
            monitor_once()
        except Exception:
            log.exception("plant monitor failed")

    def start(self) -> None:
        self.scheduler.add_job(self.tick, "interval", minutes=self.settings.schedule_minutes,
                               next_run_time=pd.Timestamp.now(tz="UTC").to_pydatetime())
        if self.settings.monitor_enabled:
            self.scheduler.add_job(self.monitor, "interval", minutes=self.settings.monitor_minutes,
                                   next_run_time=(pd.Timestamp.now(tz="UTC") + pd.Timedelta(minutes=2)).to_pydatetime(),
                                   max_instances=1, coalesce=True)
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)


def attach_loop(app) -> None:
    app.state.loop = asyncio.get_running_loop()
