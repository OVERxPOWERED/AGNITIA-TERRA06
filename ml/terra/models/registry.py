"""Artifact registry: artifacts/models/<source>/<name>/<version>/{model.joblib, meta.json}."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib

from terra.paths import ARTIFACTS


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def save_object(obj, source: str, name: str, meta: dict, version: str | None = None) -> Path:
    version = version or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    d = ARTIFACTS / "models" / source / name / version
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, d / "model.joblib")
    (d / "meta.json").write_text(json.dumps({"name": name, "source": source, "version": version,
                                             "git_sha": git_sha(), **meta}, indent=2, default=str))
    latest = d.parent / "LATEST"
    latest.write_text(version)
    return d


def load_object(source: str, ref: str):
    """ref = 'gbm@latest' or 'gbm@20261012T101500'."""
    name, _, version = ref.partition("@")
    base = ARTIFACTS / "models" / source / name
    if version in ("", "latest"):
        version = (base / "LATEST").read_text().strip()
    return joblib.load(base / version / "model.joblib")


def load_meta(source: str, ref: str) -> dict:
    name, _, version = ref.partition("@")
    base = ARTIFACTS / "models" / source / name
    if version in ("", "latest"):
        version = (base / "LATEST").read_text().strip()
    return json.loads((base / version / "meta.json").read_text())
