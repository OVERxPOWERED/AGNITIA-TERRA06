"""ForecastBundle: everything needed to turn framed rows into a calibrated ensemble forecast."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from terra.eval.backtest import align_external
from terra.features.build_features import feature_columns
from terra.models.base import ForecastModel
from terra.models.conformal import CQR
from terra.models.ensemble import Ensemble
from terra.schema import QCOLS


@dataclass
class ForecastBundle:
    source: str
    capacity_mw: float
    models: dict[str, ForecastModel]
    ensemble: Ensemble
    cqr: CQR
    features: list[str]
    meta: dict = field(default_factory=dict)

    def member_predictions(self, rows: pd.DataFrame, external: dict[str, pd.DataFrame] | None = None
                           ) -> dict[str, pd.DataFrame]:
        X = rows[self.features + ["lead_bucket"]]
        preds = {name: m.predict(X) for name, m in self.models.items()}
        for name, ext in (external or {}).items():
            preds[name] = align_external(rows, ext)
        return preds

    def predict(self, rows: pd.DataFrame, external: dict[str, pd.DataFrame] | None = None
                ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], np.ndarray]:
        """Returns (calibrated ensemble q-frame, member q-frames, model spread)."""
        preds = self.member_predictions(rows, external)
        members = {m: preds[m] for m in self.ensemble.members}
        if any(members[m][list(QCOLS)].isna().any().any() for m in members):
            raise ValueError("an ensemble member has missing predictions for some rows")
        buckets = rows["lead_bucket"].astype(str).to_numpy()
        raw = self.ensemble.predict(members, buckets)
        cal = self.cqr.apply(raw, rows, self.capacity_mw, zero_at_night=self.source == "solar")
        return cal, preds, self.ensemble.spread(members)


def check_features(rows: pd.DataFrame, bundle: ForecastBundle) -> None:
    missing = set(bundle.features) - set(feature_columns(rows))
    if missing:
        raise KeyError(f"rows missing features: {sorted(missing)}")
