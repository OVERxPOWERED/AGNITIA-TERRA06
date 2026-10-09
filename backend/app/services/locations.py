"""Live forecasts for allowlisted sites ("the same plant, somewhere else").

A request starts a background job that runs the normal forecast pipeline in live mode with only the site
block changed, writing into artifacts/runs_location/<id>/ so the main run is never touched. Results are
reused for CACHE_MINUTES. At most MAX_WORKERS jobs run at once, so the API stays responsive.
"""
from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pandas as pd
from terra.config import load_config
from terra.data.openmeteo import ATTRIBUTION
from terra.locations import Location, config_for, get_location, load_locations
from terra.logs import get_logger
from terra.paths import ARTIFACTS
from terra.pipelines.forecast import run_forecast

from app.schemas.api import (AlertOut, DispatchPoint, ForecastPoint, Kpis, LocationInfo, LocationJob,
                             LocationResult)

log = get_logger(__name__)
ROOT = ARTIFACTS / "runs_location"
CACHE_MINUTES = 30
MAX_WORKERS = 2
_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="location")
_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_latest: dict[str, str] = {}          # location id -> run dir name of the newest finished run


def _now() -> datetime:
    return datetime.now(timezone.utc)


def info(loc: Location) -> LocationInfo:
    home = load_locations()[1]
    return LocationInfo(**loc.__dict__, is_home=loc.id == home)


def list_locations() -> list[LocationInfo]:
    return [info(x) for x in load_locations()[0]]


def _view(j: dict, reused: bool = False) -> LocationJob:
    return LocationJob(job_id=j["id"], location_id=j["loc"], status=j["status"], step=j["step"],
                       started_at=j["started"].isoformat(), error=j.get("error"), reused=reused,
                       finished_at=j["finished"].isoformat() if j.get("finished") else None)


def _fresh(loc_id: str) -> dict | None:
    for j in sorted(_jobs.values(), key=lambda x: x["started"], reverse=True):
        if j["loc"] != loc_id:
            continue
        if j["status"] in ("queued", "running"):
            return j
        if j["status"] == "done" and _now() - j["finished"] < timedelta(minutes=CACHE_MINUTES):
            return j
        break
    return None


def _run(job: dict) -> None:
    loc = get_location(job["loc"])
    try:
        job["status"] = "running"
        cfg = config_for(load_config(), loc)
        out = run_forecast(cfg, "live", runs_dir=ROOT / loc.id, write_latest=False,
                           progress=lambda s: job.__setitem__("step", s))
        _latest[loc.id] = out.name
        job.update(status="done", step="done", finished=_now())
    except Exception as exc:  # noqa: BLE001
        log.exception("location forecast failed for %s", loc.id)
        job.update(status="failed", error=f"{type(exc).__name__}: {exc}", finished=_now())


def submit(loc_id: str, force: bool = False) -> LocationJob | None:
    loc = get_location(loc_id)
    if loc is None:
        return None
    with _lock:
        j = None if force else _fresh(loc_id)
        if j is not None:
            return _view(j, reused=True)
        j = {"id": uuid.uuid4().hex[:12], "loc": loc_id, "status": "queued", "step": "queued", "started": _now()}
        _jobs[j["id"]] = j
        _pool.submit(_run, j)
        return _view(j)


def job(job_id: str) -> LocationJob | None:
    j = _jobs.get(job_id)
    return _view(j) if j else None


def _points(df: pd.DataFrame, source: str) -> list[ForecastPoint]:
    d = df[df["source"] == source].sort_values("lead_h").copy()
    d["target_time_utc"] = d["target_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    cols = ["target_time_utc", "lead_h", "q05", "q10", "q50", "q90", "q95", "trust_score", "trust_level", "trust_reason"]
    return [ForecastPoint(**r) for r in d[cols].to_dict(orient="records")]


def result(loc_id: str) -> LocationResult | None:
    loc = get_location(loc_id)
    name = _latest.get(loc_id)
    if loc is None or name is None:
        return None
    d = ROOT / loc_id / name
    meta = json.loads((d / "run.json").read_text())
    fc = pd.read_parquet(d / "forecast.parquet")
    disp = pd.read_parquet(d / "dispatch.parquet")
    disp = disp[disp["strategy"] == "advisor"].copy()
    disp["target_time_utc"] = disp["target_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    kp = json.loads((d / "dispatch_kpis.json").read_text())["advisor"]
    alerts = [AlertOut(**{**a, "acknowledged": False}) for a in json.loads((d / "alerts.json").read_text())]
    home = info(loc).is_home
    caveat = ("This is the home site. The models were trained and tested here, on real weather and a virtual twin plant."
              if home else
              "The same virtual plant is placed at this site. The models were trained and tested only at Dewas, "
              "so accuracy here is not validated. Treat it as a live what-if, not a verified forecast.")
    return LocationResult(
        location=info(loc), issue_time_utc=meta["issue_time_utc"], generated_at=meta["created_at"],
        solar=_points(fc, "solar"), wind=_points(fc, "wind"), hybrid=_points(fc, "hybrid"),
        dispatch=[DispatchPoint(**r) for r in disp[list(DispatchPoint.model_fields)].to_dict(orient="records")],
        kpis=Kpis(**kp), alerts=alerts, validated_here=home, caveat=caveat, attribution=ATTRIBUTION)
