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
