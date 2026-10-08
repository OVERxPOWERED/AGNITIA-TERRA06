"""Read-only access to forecast runs, backtests and evaluation artifacts written by the ML package."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
from terra.config import load_config
from terra.eval.metrics import metrics_table
from terra.paths import ARTIFACTS, DOCS

RUNS = ARTIFACTS / "runs"


class NoRunYet(FileNotFoundError):
    pass


def latest_name() -> str:
    p = RUNS / "LATEST"
    if not p.exists():
        raise NoRunYet("no forecast run yet - run `terra forecast` or wait for the scheduler")
    return p.read_text().strip()


@lru_cache(maxsize=16)
def _load(name: str) -> dict:
    d = RUNS / name
    out = {"name": name, "meta": json.loads((d / "run.json").read_text()),
           "forecast": pd.read_parquet(d / "forecast.parquet"),
           "alerts": json.loads((d / "alerts.json").read_text()),
           "dispatch": pd.read_parquet(d / "dispatch.parquet"),
           "dispatch_kpis": json.loads((d / "dispatch_kpis.json").read_text()),
           "rows": {s: pd.read_parquet(d / f"rows_{s}.parquet") for s in ("solar", "wind")}}
    p = d / "dsm_schedule.parquet"
    out["dsm_schedule"] = pd.read_parquet(p) if p.exists() else None
    return out


def latest() -> dict:
    return _load(latest_name())


@lru_cache(maxsize=2)
def backtest(source: str) -> pd.DataFrame:
    p = ARTIFACTS / "backtests" / source / "predictions.parquet"
    if not p.exists():
        raise NoRunYet(f"no backtest for {source} - run `terra train`")
    return pd.read_parquet(p)


@lru_cache(maxsize=1)
def evaluation() -> dict:
    p = ARTIFACTS / "evaluation" / "results.json"
    if not p.exists():
        raise NoRunYet("no evaluation yet - run `terra evaluate`")
    return json.loads(p.read_text())


@lru_cache(maxsize=16)
def compare_models(source: str, split: str = "test", by: str | None = None, daylight: bool = False) -> pd.DataFrame:
    cfg = load_config()
    p = backtest(source)
    p = p[p["split"] == split]
    is_daylight = daylight and source == "solar"
    return metrics_table(p, cfg.capacity_mw(source), by=[by] if by else None, daylight_only=is_daylight)


def read_doc(name: str) -> str:
    p = DOCS / name
    return p.read_text(encoding="utf-8") if p.exists() else f"_{name} not generated yet_"


def clear_cache() -> None:
    _load.cache_clear()
    backtest.cache_clear()
    evaluation.cache_clear()
    compare_models.cache_clear()


def run_dir(name: str) -> Path:
    return RUNS / name
