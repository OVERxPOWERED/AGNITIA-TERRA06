"""What-if service: loads models once, caches results per (run, scenario)."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import numpy as np
from terra.config import load_config
from terra.data.build_dataset import load_dataset
from terra.engines.whatif import Scenario, run_whatif
from terra.models.registry import load_object

from app.services import runs

_cache: dict[str, dict] = {}


@lru_cache(maxsize=1)
def _models() -> tuple[dict, dict]:
    bundles = {s: load_object(s, "bundle@latest") for s in ("solar", "wind")}
    return bundles, load_object("hybrid", "engines@latest")


def whatif_job(sc: Scenario, job_id: str) -> dict | None:
    """What-if on a live run for the operator's plant (the job's rows, plant factors, battery and demand)."""
    import pandas as pd
    from terra.locations import get_location
    from terra.profile import apply_profile

    from app.services import locations as loc_svc

    d, job = loc_svc.run_dir(job_id)
    if d is None:
        return None
    key = f"job:{job_id}:" + hashlib.sha256(json.dumps(sc.model_dump(), sort_keys=True).encode()).hexdigest()[:16]
    if key in _cache:
        return _cache[key]
    applied = apply_profile(load_config(), get_location(job["loc"]), job["clean"], job["calibration"])
    bundles, engines = _models()
    rows = {s: pd.read_parquet(d / f"rows_{s}.parquet") for s in ("solar", "wind")}
    fc = pd.read_parquet(d / "forecast.parquet")
    factor = {s: fc[fc["source"] == s].sort_values("lead_h")["plant_factor"].to_numpy() for s in ("solar", "wind")}
    disp = pd.read_parquet(d / "dispatch.parquet")
    demand = disp[disp["strategy"] == "advisor"].sort_values("target_time_utc")["demand_mw"].to_numpy()
    res = run_whatif(applied.model_cfg, rows, bundles, engines, demand, sc, plant_factor=factor, plant_cfg=applied.user_cfg)
    _cache[key] = res
    return res


def whatif(sc: Scenario) -> dict:
    run = runs.latest()
    key = run["name"] + hashlib.sha256(json.dumps(sc.model_dump(), sort_keys=True).encode()).hexdigest()[:16]
    if key in _cache:
        return _cache[key]
    cfg = load_config()
    bundles, engines = _models()
    rows = run["rows"]
    targets = rows["solar"]["target_time_utc"]
    try:
        demand = load_dataset()["demand_mw"].reindex(targets).to_numpy()
    except FileNotFoundError:
        demand = np.full(len(targets), cfg.demand.peak_mw * 0.8)
    res = run_whatif(cfg, rows, bundles, engines, np.nan_to_num(demand, nan=cfg.demand.peak_mw * 0.8), sc)
    if len(_cache) > 256:
        _cache.clear()
    _cache[key] = res
    return res
