"""M4 ensemble: per-lead-bucket non-negative weights over member models (quantile averaging)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from terra.eval.metrics import pinball_multi
from terra.schema import QCOLS, QUANTILES


def _softmax(z: np.ndarray) -> np.ndarray:
    e = np.exp(z - z.max())
    return e / e.sum()


class Ensemble:
    name = "ensemble"

    def __init__(self, members: list[str]):
        self.members = members
        self.weights: dict[str, np.ndarray] = {}

    def fit(self, preds: dict[str, pd.DataFrame], y: np.ndarray, buckets: np.ndarray) -> "Ensemble":
        """preds[m] = DataFrame[q05..q95] aligned row-by-row with y (validation split)."""
        stack = np.stack([preds[m][list(QCOLS)].to_numpy() for m in self.members])   # (M, N, Q)
        for b in np.unique(buckets):
            sel = buckets == b
            def loss(z: np.ndarray) -> float:
                w = _softmax(z)
                q = np.tensordot(w, stack[:, sel, :], axes=1)
                return pinball_multi(y[sel], q, QUANTILES)
            res = minimize(loss, np.zeros(len(self.members)), method="Nelder-Mead",
                           options={"maxiter": 400, "xatol": 1e-4, "fatol": 1e-6})
            self.weights[str(b)] = _softmax(res.x)
        return self

    def predict(self, preds: dict[str, pd.DataFrame], buckets: np.ndarray) -> pd.DataFrame:
        stack = np.stack([preds[m][list(QCOLS)].to_numpy() for m in self.members])
        out = np.zeros(stack.shape[1:])
        for b, w in self.weights.items():
            sel = buckets == b
            out[sel] = np.tensordot(w, stack[:, sel, :], axes=1)
        out = np.sort(out, axis=1)
        return pd.DataFrame(out, columns=list(QCOLS), index=next(iter(preds.values())).index)

    def spread(self, preds: dict[str, pd.DataFrame]) -> np.ndarray:
        """Std of member medians — the model-disagreement signal used by the Trust engine."""
        return np.std(np.stack([preds[m]["q50"].to_numpy() for m in self.members]), axis=0)

    def weights_table(self) -> pd.DataFrame:
        return pd.DataFrame(self.weights, index=self.members).T
