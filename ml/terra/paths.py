"""Repository-relative paths. Import these constants instead of hard-coding paths."""
from __future__ import annotations

import os
from pathlib import Path

# ml/terra/paths.py -> parents[2] is the repo root
REPO_ROOT = Path(os.environ.get("TERRA_REPO_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = Path(os.environ.get("TERRA_DATA_DIR", REPO_ROOT / "data"))
DATA_RAW = DATA_DIR / "raw"
DATA_EXTERNAL = DATA_DIR / "external"
DATA_INTERIM = DATA_DIR / "interim"
DATA_PROCESSED = DATA_DIR / "processed"
DATA_SAMPLES = DATA_DIR / "samples"
ARTIFACTS = Path(os.environ.get("TERRA_ARTIFACTS_DIR", REPO_ROOT / "artifacts"))
DOCS = REPO_ROOT / "docs"
DOCS_IMAGES = DOCS / "images"


def ensure_dirs() -> None:
    """Create all writable directories (safe to call repeatedly)."""
    for p in (DATA_RAW, DATA_EXTERNAL, DATA_INTERIM, DATA_PROCESSED, DATA_SAMPLES, ARTIFACTS, DOCS_IMAGES):
        p.mkdir(parents=True, exist_ok=True)
