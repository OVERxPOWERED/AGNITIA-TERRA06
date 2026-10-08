"""Conformalized quantile regression (CQR): recalibrate bands to hit nominal coverage.

For each interval (q10,q90 -> 80%) and (q05,q95 -> 90%) and each group (lead_bucket x is_day):
  score_i = max(lo_i - y_i, y_i - hi_i);  Q = quantile(scores, ceil((n+1)(1-alpha))/n)
  lo -= Q; hi += Q          (Q < 0 shrinks an over-wide band)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

INTERVALS = (("q10", "q90", 0.20), ("q05", "q95", 0.10))


class CQR:
    def __init__(self) -> None:
        self.adj: dict[tuple[str, str, int], float] = {}

    @staticmethod
    def _groups(meta: pd.DataFrame) -> list[tuple[str, int]]:
        day = meta["cal_is_day"] if "cal_is_day" in meta else pd.Series(1, index=meta.index)
        return list(zip(meta["lead_bucket"].astype(str), day.astype(int)))

    def fit(self, q: pd.DataFrame, y: np.ndarray, meta: pd.DataFrame) -> "CQR":
        groups = np.array(self._groups(meta), dtype=object)
        keys = pd.Series([f"{a}|{b}" for a, b in groups])
        for lo, hi, alpha in INTERVALS:
            scores = np.maximum(q[lo].to_numpy() - y, y - q[hi].to_numpy())
            for k in keys.unique():
                s = scores[(keys == k).to_numpy()]
                n = len(s)
                level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
                b, d = k.split("|")
                self.adj[(lo, b, int(d))] = float(np.quantile(s, level))
        return self

    def apply(self, q: pd.DataFrame, meta: pd.DataFrame, capacity: float,
              zero_at_night: bool = False) -> pd.DataFrame:
        out = q.copy()
        groups = self._groups(meta)
        for lo, hi, _ in INTERVALS:
            a = np.array([self.adj.get((lo, b, d), 0.0) for b, d in groups])
            out[lo] = out[lo].to_numpy() - a
            out[hi] = out[hi].to_numpy() + a
        arr = np.sort(np.clip(out.to_numpy(), 0, capacity), axis=1)
        if zero_at_night and "cal_is_day" in meta:
            arr[meta["cal_is_day"].to_numpy() == 0] = 0.0
        return pd.DataFrame(arr, index=q.index, columns=q.columns)
