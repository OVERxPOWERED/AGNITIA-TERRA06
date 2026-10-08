"""Feature selection helpers on top of the framed table."""
from __future__ import annotations

import pandas as pd

from terra.data.quality import assert_no_leakage
from terra.schema import is_feature


def feature_columns(frame: pd.DataFrame) -> list[str]:
    cols = [c for c in frame.columns if is_feature(c)]
    assert_no_leakage(cols)
    return cols


def xy(frame: pd.DataFrame, split: str | None = None) -> tuple[pd.DataFrame, pd.Series]:
    """X = feature columns + 'lead_bucket' (metadata used for bands/conformal, ignored by GBM)."""
    f = frame if split is None else frame[frame["split"] == split]
    return f[feature_columns(f) + ["lead_bucket"]], f["y"]
