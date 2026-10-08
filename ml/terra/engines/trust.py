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


def hybrid_trust_score(
    q50_solar: np.ndarray | float,
    q50_wind: np.ndarray | float,
    trust_solar: np.ndarray | float,
    trust_wind: np.ndarray | float,
) -> np.ndarray | float:
    """Expected-generation-weighted average of solar and wind trust scores.

    trust_h = (w_solar * trust_solar + w_wind * trust_wind) / (w_solar + w_wind)
    where w_s = q50_s (MW) per hour. When both q50 are ~0 (< 1e-6), falls back to
    the plain mean (trust_solar + trust_wind) / 2. Output is clipped to [0, 100]
    and rounded to 0 decimals.
    """
    qs = np.asarray(q50_solar, dtype=float)
    qw = np.asarray(q50_wind, dtype=float)
    ts = np.asarray(trust_solar, dtype=float)
    tw = np.asarray(trust_wind, dtype=float)

    total_q = qs + qw
    is_scalar = total_q.ndim == 0

    plain_mean = (ts + tw) / 2.0
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = np.where(total_q < 1e-6, 1.0, total_q)
        weighted = (qs * ts + qw * tw) / denom

    score = np.where(total_q < 1e-6, plain_mean, weighted)
    score = np.clip(score, 0.0, 100.0).round(0)

    return float(score) if is_scalar else score

