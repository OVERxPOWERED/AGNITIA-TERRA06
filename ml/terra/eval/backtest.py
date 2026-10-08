"""Backtest helpers: long-format predictions for many models on one split."""
from __future__ import annotations

import pandas as pd

from terra.schema import QCOLS

META_COLS = ["issue_time_utc", "target_time_utc", "lead_h", "lead_bucket", "cal_is_day", "split", "y"]


def long_predictions(frame: pd.DataFrame, preds: dict[str, pd.DataFrame], source: str) -> pd.DataFrame:
    """Stack {model: q-frame aligned with frame rows} into one long table with metadata."""
    parts = []
    meta = frame[META_COLS].reset_index(drop=True)
    for name, q in preds.items():
        p = pd.concat([meta, q[list(QCOLS)].reset_index(drop=True)], axis=1)
        p["model"] = name
        p["source"] = source
        parts.append(p)
    return pd.concat(parts, ignore_index=True)


def align_external(frame: pd.DataFrame, ext: pd.DataFrame) -> pd.DataFrame:
    """Align externally produced predictions (e.g. Chronos-2, keyed by issue/target) to frame rows."""
    keys = ["issue_time_utc", "target_time_utc"]
    m = frame[keys].merge(ext[keys + list(QCOLS)], on=keys, how="left")
    m.index = frame.index
    return m[list(QCOLS)]
