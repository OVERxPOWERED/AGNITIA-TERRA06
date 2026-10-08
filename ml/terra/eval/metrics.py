"""Forecast metrics. All functions take numpy arrays in MW."""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from terra.schema import QCOLS, QUANTILES


def mae(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(np.abs(y - p)))


def rmse(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - p) ** 2)))


def bias(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(p - y))


def pinball(y: np.ndarray, q_pred: np.ndarray, alpha: float) -> float:
    d = y - q_pred
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


def pinball_multi(y: np.ndarray, q: np.ndarray, alphas: Sequence[float]) -> float:
    """Mean pinball loss over all quantile columns of q (shape N x Q)."""
    return float(np.mean([pinball(y, q[:, i], a) for i, a in enumerate(alphas)]))


def picp(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((y >= lo) & (y <= hi)))


def mpiw(lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean(hi - lo))


def summary(df: pd.DataFrame, capacity: float) -> dict[str, float]:
    """df has columns y, q05..q95. Returns the standard metric dict."""
    y = df["y"].to_numpy(float)
    p = df["q50"].to_numpy(float)
    q = df[list(QCOLS)].to_numpy(float)
    return {
        "n": int(len(df)),
        "mae": mae(y, p), "rmse": rmse(y, p), "bias": bias(y, p),
        "nmae_pct": 100 * mae(y, p) / capacity, "nrmse_pct": 100 * rmse(y, p) / capacity,
        "pinball": pinball_multi(y, q, QUANTILES),
        "picp80": picp(y, df["q10"].to_numpy(), df["q90"].to_numpy()),
        "picp90": picp(y, df["q05"].to_numpy(), df["q95"].to_numpy()),
        "mpiw80_pct": 100 * mpiw(df["q10"].to_numpy(), df["q90"].to_numpy()) / capacity,
    }


def skill(model_mae: float, baseline_mae: float) -> float:
    return float(1.0 - model_mae / baseline_mae) if baseline_mae > 0 else float("nan")


def metrics_table(preds: pd.DataFrame, capacity: float, by: list[str] | None = None,
                  baseline: str = "persistence", daylight_only: bool = False) -> pd.DataFrame:
    """preds: long table with columns model, y, q05..q95 [, lead_bucket, cal_is_day ...]."""
    p = preds[preds["cal_is_day"] == 1] if daylight_only and "cal_is_day" in preds else preds
    keys = ["model"] + (by or [])
    rows = [{**dict(zip(keys, k if isinstance(k, tuple) else (k,))), **summary(g, capacity)}
            for k, g in p.groupby(keys, sort=True)]
    t = pd.DataFrame(rows)
    if baseline in set(t["model"]):
        base = t[t["model"] == baseline].set_index(by or ["model"])["mae"] if by else \
            t.loc[t["model"] == baseline, "mae"].iloc[0]
        if by:
            t["skill_vs_persistence"] = [skill(r["mae"], base.loc[tuple(r[b] for b in by)] if len(by) > 1
                                               else base.loc[r[by[0]]]) for _, r in t.iterrows()]
        else:
            t["skill_vs_persistence"] = [skill(m, base) for m in t["mae"]]
    return t
