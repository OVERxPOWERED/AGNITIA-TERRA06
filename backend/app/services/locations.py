"""Live forecasts for allowlisted sites, optionally with the operator's plant profile applied.

A request starts a background job that runs the normal forecast pipeline in live mode, writing into
artifacts/runs_location/<site>/<profile hash>/ so the main run is never touched. The profile arrives with the
request (the browser holds it), so the server stays stateless and one visitor cannot change another's plant.
Results are reused for CACHE_MINUTES per (site, profile). At most MAX_WORKERS jobs run at once.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pandas as pd
from terra.config import load_config
from terra.data.openmeteo import ATTRIBUTION
from terra.data.weather_models import LABELS
from terra.locations import Location, get_location, load_locations
from terra.logs import get_logger
from terra.paths import ARTIFACTS
from terra.pipelines.forecast import run_forecast
from terra.profile import NAME_ONLY, apply_profile, defaults, schema, validate

from app.schemas.api import (
    AlertOut,
    BlockPoint,
    DispatchPoint,
    ForecastPoint,
    Kpis,
    LocationInfo,
    LocationJob,
    LocationResult,
    PlantSummary,
    ProfileCheck,
    WeatherModelPoint,
    WeatherModelSeries,
)

log = get_logger(__name__)
ROOT = ARTIFACTS / "runs_location"
CACHE_MINUTES = 30
MAX_WORKERS = 2
_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="location")
_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def info(loc: Location) -> LocationInfo:
    home = load_locations()[1]
    return LocationInfo(**loc.__dict__, is_home=loc.id == home)


def list_locations() -> list[LocationInfo]:
    return [info(x) for x in load_locations()[0]]


def _home() -> str:
    return load_locations()[1]


def profile_schema() -> dict:
    return schema(load_config(), _home())


def _summary(loc: Location, clean: dict, calibration: dict | None = None) -> PlantSummary:
    a = apply_profile(load_config(), loc, clean, calibration)
    base = defaults(load_config(), _home())
    changed = [k for k, v in clean.items() if k in base and v != base[k] and k not in NAME_ONLY]
    return PlantSummary(**{k: v for k, v in a.summary.items() if k != "location"}, location=loc.name,
                        entered=sorted(clean), customised=bool(changed) or bool(a.calibration))


def check_profile(values: dict, location_id: str | None = None) -> ProfileCheck:
    ids = {x.id for x in load_locations()[0]}
    clean, errors = validate(values, load_config(), _home(), ids)
    loc = get_location(location_id or clean.get("location_id") or _home())
    return ProfileCheck(clean=clean, errors=errors, summary=_summary(loc, clean) if loc and not errors else None)


def _key(clean: dict, calibration: dict, keys: dict) -> str:
    blob = json.dumps({"p": clean, "c": calibration, "k": {n: hashlib.sha256(v.encode()).hexdigest() for n, v in keys.items()}},
                      sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:10]


def clean_calibration(c: dict | None) -> dict[str, float]:
    out = {}
    for k, v in (c or {}).items():
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if k in ("solar", "wind") and 0.3 <= x <= 1.6:
            out[k] = x
    return out


def _view(j: dict, reused: bool = False) -> LocationJob:
    return LocationJob(job_id=j["id"], location_id=j["loc"], status=j["status"], step=j["step"],
                       started_at=j["started"].isoformat(), error=j.get("error"), reused=reused,
                       finished_at=j["finished"].isoformat() if j.get("finished") else None)


def _fresh(loc_id: str, key: str) -> dict | None:
    for j in sorted(_jobs.values(), key=lambda x: x["started"], reverse=True):
        if j["loc"] != loc_id or j["key"] != key:
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
        applied = apply_profile(load_config(), loc, job["clean"], job["calibration"])
        out = run_forecast(applied.user_cfg, "live", runs_dir=ROOT / loc.id / job["key"], write_latest=False,
                           progress=lambda s: job.__setitem__("step", s), model_cfg=applied.model_cfg,
                           adjust=applied, second_opinions=True, api_keys=job["keys"], site_id=loc.id)
        job["keys"] = {}                                    # provider keys are used once and dropped
        if job.get("user_id"):                              # signed in: check against the schedule they submitted
            from app.services.notify import deviation_alerts_for_run
            extra = deviation_alerts_for_run(job["user_id"], out, applied.summary["solar_ac_mw"] + applied.summary["wind_mw"],
                                             applied.summary["plant_name"])
            if extra:
                al = json.loads((out / "alerts.json").read_text())
                (out / "alerts.json").write_text(json.dumps(extra + al, indent=2))
        job.update(status="done", step="done", finished=_now(), run_dir=out)
    except Exception as exc:
        log.exception("location forecast failed for %s", loc.id)
        msg = f"{type(exc).__name__}: {exc}"
        if "429" in msg:
            msg = ("The free weather service (Open-Meteo) is rate-limiting this server right now. "
                   "Try again in a few minutes. " + msg[:120])
        job.update(status="failed", error=msg, finished=_now())


def submit(loc_id: str, values: dict | None = None, force: bool = False, calibration: dict | None = None,
           keys: dict | None = None, user_id: str | None = None) -> LocationJob | ProfileCheck | None:
    loc = get_location(loc_id)
    if loc is None:
        return None
    chk = check_profile(values or {}, loc_id)
    if chk.errors:
        return chk
    clean = {k: v for k, v in chk.clean.items() if k != "location_id"}
    cal = clean_calibration(calibration)
    keys = {k: str(v).strip() for k, v in (keys or {}).items() if k in ("solcast", "tomorrow") and str(v).strip()}
    key = _key(clean, cal, keys) + (f"-{user_id[:8]}" if user_id else "")
    with _lock:
        j = None if force else _fresh(loc_id, key)
        if j is not None:
            return _view(j, reused=True)
        j = {"id": uuid.uuid4().hex[:12], "loc": loc_id, "key": key, "clean": clean, "calibration": cal, "keys": keys,
             "user_id": user_id, "status": "queued",
             "step": "queued", "started": _now()}
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


def _blocks(p) -> list[BlockPoint]:
    if not p.exists():
        return []
    b = pd.read_parquet(p)
    t = pd.to_datetime(b["block_end_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return [BlockPoint(block_end_utc=x, solar=round(float(s), 3), wind=round(float(w), 3), hybrid=round(float(h), 3))
            for x, s, w, h in zip(t, b.get("solar", 0 * b["hybrid"]), b.get("wind", 0 * b["hybrid"]), b["hybrid"])]


def run_dir(job_id: str):
    j = _jobs.get(job_id)
    return (j["run_dir"], j) if j and j["status"] == "done" else (None, None)


def result(job_id: str) -> LocationResult | None:
    j = _jobs.get(job_id)
    if j is None or j["status"] != "done":
        return None
    loc = get_location(j["loc"])
    d = j["run_dir"]
    meta = json.loads((d / "run.json").read_text())
    fc = pd.read_parquet(d / "forecast.parquet")
    disp = pd.read_parquet(d / "dispatch.parquet")
    disp["target_time_utc"] = disp["target_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    by = {k: [DispatchPoint(**r) for r in g[list(DispatchPoint.model_fields)].to_dict(orient="records")]
          for k, g in disp.groupby("strategy")}
    kall = {k: Kpis(**v) for k, v in json.loads((d / "dispatch_kpis.json").read_text()).items()}
    alerts = [AlertOut(**{**a, "acknowledged": False}) for a in json.loads((d / "alerts.json").read_text())]
    plant = _summary(loc, j["clean"], j["calibration"])
    hyb = fc[fc["source"] == "hybrid"].sort_values("lead_h")
    curtailed = hyb["export_curtailed_mw"].fillna(0).round(3).tolist() if "export_curtailed_mw" in hyb else []
    second = []
    status_p, table_p = d / "weather_models.json", d / "weather_models.parquet"
    status = json.loads(status_p.read_text()) if status_p.exists() else {}
    if table_p.exists():
        t = pd.read_parquet(table_p)
        t["target_time_utc"] = pd.to_datetime(t["target_time_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        t = t.astype(object).where(t.notna(), None)
        for m, g in t.groupby("model", sort=False):
            pts = [WeatherModelPoint(**r) for r in g[list(WeatherModelPoint.model_fields)].to_dict(orient="records")]
            second.append(WeatherModelSeries(id=m, label=LABELS.get(m, m), status=status.get(m, "ok"), points=pts))
    for m, st in status.items():
        if not any(x.id == m for x in second):
            second.append(WeatherModelSeries(id=m, label=LABELS.get(m, m), status=st, points=[]))
    home = info(loc).is_home
    caveat = ("This is the home site. The models were trained and tested here, on real weather and a virtual twin plant."
              if home else
              "The models were trained and tested only at Dewas, so accuracy here is not validated. "
              "Treat it as a live what-if, not a verified forecast.")
    if plant.customised:
        caveat += (" Your plant's layout is applied through the physics model (the hourly ratio of your plant's physics "
                   "output to the trained plant's), then equipment availability, panel condition and calibration; "
                   "battery, demand and alert settings come from your plant profile.")
    return LocationResult(
        location=info(loc), issue_time_utc=meta["issue_time_utc"], generated_at=meta["created_at"],
        solar=_points(fc, "solar"), wind=_points(fc, "wind"), hybrid=_points(fc, "hybrid"),
        dispatch=by["advisor"], kpis=kall["advisor"], dispatch_by_strategy=by, kpis_by_strategy=kall, alerts=alerts, validated_here=home and not plant.customised, caveat=caveat,
        attribution=ATTRIBUTION, plant=plant, second_opinions=second, export_curtailed_mw=curtailed,
        export_curtailed_mwh=round(float(sum(curtailed)), 2), dsm_schedule=_blocks(d / "dsm_schedule.parquet"),
        expected_blocks=_blocks(d / "blocks_p50.parquet"))
