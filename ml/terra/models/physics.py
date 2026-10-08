"""M1: physics model = digital twin applied to the forecast weather (feature phys_mw)."""
from __future__ import annotations

import pandas as pd

from terra.models.base import ForecastModel, ResidualBands, finalize_quantiles, to_qframe


class Physics(ForecastModel):
    name = "physics"

    def fit(self, X, y, X_val=None, y_val=None):
        Xb, yb = (X_val, y_val) if X_val is not None else (X, y)
        self.bands = ResidualBands().fit(Xb, yb.to_numpy() - Xb["phys_mw"].to_numpy())
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        point = X["phys_mw"].to_numpy(float)
        q = finalize_quantiles(self.bands.apply(X, point), self.capacity_mw, self.night_mask(X))
        return to_qframe(q, X.index)
