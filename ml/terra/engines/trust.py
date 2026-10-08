"""H3 Trust engine: per-hour reliability score 0-100 that ranks hours by expected error.

Inputs per hour: relative band width, model disagreement, lead time, recent error.
Weights are fitted with non-negative least squares to predict |error| / capacity on validation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import nnls

FEATURES = ("band_width", "spread", "lead", "recent_err")
REASONS = {
    "band_width": "wide uncertainty band",
    "spread": "models disagree",
    "lead": "far-ahead hour",
    "recent_err": "recent forecasts were off",
}


def trust_features(q: pd.DataFrame, spread: np.ndarray, lead_h: np.ndarray, recent_err_frac: np.ndarray,
                   capacity: float) -> pd.DataFrame:
    return pd.DataFrame({
        "band_width": (q["q90"].to_numpy() - q["q10"].to_numpy()) / capacity,
        "spread": spread / capacity,
        "lead": lead_h / 48.0,
        "recent_err": recent_err_frac,
    }, index=q.index)


@dataclass
class TrustModel:
    weights: np.ndarray = field(default_factory=lambda: np.array([1.0, 1.0, 0.02, 0.5]))
    err_ref: float = 0.15                   # |error|/capacity that maps to score 0

    def fit(self, feats: pd.DataFrame, abs_err_frac: np.ndarray) -> "TrustModel":
        A = feats[list(FEATURES)].to_numpy()
        self.weights, _ = nnls(A, abs_err_frac)
        pred = A @ self.weights
        self.err_ref = float(max(np.quantile(pred, 0.95), 1e-6))
        return self

    def score(self, feats: pd.DataFrame) -> np.ndarray:
        pred = feats[list(FEATURES)].to_numpy() @ self.weights
        return np.clip(100 * (1 - pred / self.err_ref), 0, 100).round(0)

    def explain(self, feats: pd.DataFrame) -> list[str]:
        contrib = feats[list(FEATURES)].to_numpy() * self.weights
        return [REASONS[FEATURES[int(np.argmax(c))]] if c.max() > 0 else "stable conditions" for c in contrib]


def level(score: float) -> str:
    return "high" if score >= 70 else ("medium" if score >= 40 else "low")


def recent_error(history: pd.DataFrame, capacity: float, window_h: int = 168) -> float:
    """Mean |y - q50| / capacity over the last `window_h` hours of a history table (y, q50)."""
    h = history.dropna(subset=["y", "q50"]).tail(window_h)
    return float((h["y"] - h["q50"]).abs().mean() / capacity) if len(h) else 0.05
