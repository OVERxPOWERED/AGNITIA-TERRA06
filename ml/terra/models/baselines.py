"""M0 baselines: persistence and 7-day same-hour mean, with empirical residual bands."""
from __future__ import annotations

import numpy as np
import pandas as pd

from terra.models.base import ForecastModel, ResidualBands, finalize_quantiles, to_qframe


class _PointPlusBands(ForecastModel):
    point_col = ""

    def _point(self, X: pd.DataFrame) -> np.ndarray:
        return X[self.point_col].fillna(X.get("hist_mean24", 0)).to_numpy(float)

    def fit(self, X, y, X_val=None, y_val=None):
        # bands are fitted on validation if given (honest out-of-sample residuals), else on train
        Xb, yb = (X_val, y_val) if X_val is not None else (X, y)
        self.bands = ResidualBands().fit(Xb, yb.to_numpy() - self._point(Xb))
        return self

    def predict(self, X):
        q = self.bands.apply(X, self._point(X))
        q = finalize_quantiles(q, self.capacity_mw, self.night_mask(X))
        return to_qframe(q, X.index)


class Persistence(_PointPlusBands):
    """Same hour on the most recent fully observed day."""
    name = "persistence"
    point_col = "hist_lag_day"


class WeekMean(_PointPlusBands):
    """Mean of the same hour over the last 7 observed days (seasonal naive)."""
    name = "week_mean"
    point_col = "hist_lag_week_mean"
