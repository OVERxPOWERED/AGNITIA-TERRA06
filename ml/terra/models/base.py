"""Common model interface. Every model returns quantiles q05,q10,q50,q90,q95 in MW."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from terra.schema import QCOLS, QUANTILES


def finalize_quantiles(q: np.ndarray, capacity: float, night: np.ndarray | None = None) -> np.ndarray:
    """Sort each row (removes quantile crossing), clip to [0, capacity], zero at night."""
    q = np.sort(np.asarray(q, float), axis=1)
    q = np.clip(q, 0.0, capacity)
    if night is not None:
        q[np.asarray(night, bool)] = 0.0
    return q


def to_qframe(q: np.ndarray, index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(q, index=index, columns=list(QCOLS))


class ForecastModel(ABC):
    """fit(X, y) on framed features; predict(X) -> DataFrame[q05..q95]."""

    name: str = "base"

    def __init__(self, capacity_mw: float, source: str):
        self.capacity_mw = capacity_mw
        self.source = source
        self.meta: dict = {}

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, X_val: pd.DataFrame | None = None,
            y_val: pd.Series | None = None) -> "ForecastModel": ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.DataFrame: ...

    def night_mask(self, X: pd.DataFrame) -> np.ndarray | None:
        if self.source == "solar" and "cal_is_day" in X:
            return X["cal_is_day"].to_numpy() == 0
        return None

    def save(self, directory: str | Path) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, d / "model.joblib")
        (d / "meta.json").write_text(json.dumps({"name": self.name, "source": self.source,
                                                 "capacity_mw": self.capacity_mw, **self.meta},
                                                indent=2, default=str))
        return d

    @staticmethod
    def load(directory: str | Path) -> "ForecastModel":
        return joblib.load(Path(directory) / "model.joblib")


class ResidualBands:
    """Empirical residual quantiles per (lead_bucket, is_day) added around a point forecast."""

    def __init__(self) -> None:
        self.table: dict[tuple[str, int], np.ndarray] = {}
        self.default = np.zeros(len(QUANTILES))

    @staticmethod
    def _keys(X: pd.DataFrame) -> list[tuple[str, int]]:
        buckets = X["lead_bucket"] if "lead_bucket" in X else pd.Series("all", index=X.index)
        day = X["cal_is_day"] if "cal_is_day" in X else pd.Series(1, index=X.index)
        return list(zip(buckets.astype(str), day.astype(int)))

    def fit(self, X: pd.DataFrame, resid: np.ndarray) -> "ResidualBands":
        keys = self._keys(X)
        df = pd.DataFrame({"k": keys, "r": resid})
        for k, g in df.groupby("k"):
            self.table[k] = np.quantile(g["r"].to_numpy(), QUANTILES)
        self.default = np.quantile(resid, QUANTILES)
        return self

    def apply(self, X: pd.DataFrame, point: np.ndarray) -> np.ndarray:
        offs = np.stack([self.table.get(k, self.default) for k in self._keys(X)])
        offs = offs - offs[:, [2]]            # centre on the median residual
        return point[:, None] + offs
