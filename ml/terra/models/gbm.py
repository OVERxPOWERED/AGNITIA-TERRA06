"""M2: LightGBM quantile regression, one booster per quantile."""
from __future__ import annotations

import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from terra.logs import get_logger
from terra.models.base import ForecastModel, finalize_quantiles, to_qframe
from terra.schema import QUANTILES

log = get_logger(__name__)

DEFAULT_PARAMS = dict(n_estimators=3000, learning_rate=0.03, num_leaves=63, min_child_samples=50,
                      subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                      verbose=-1, n_jobs=-1, random_state=42)


class GBMQuantile(ForecastModel):
    name = "gbm"

    def __init__(self, capacity_mw: float, source: str, params: dict | None = None,
                 early_stopping_rounds: int = 100):
        super().__init__(capacity_mw, source)
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.early_stopping_rounds = early_stopping_rounds
        self.models: dict[float, lgb.LGBMRegressor] = {}
        self.features: list[str] = []

    def _prep(self, X: pd.DataFrame) -> pd.DataFrame:
        return X[self.features].astype("float32")

    def fit(self, X, y, X_val=None, y_val=None):
        self.features = [c for c in X.columns if c != "lead_bucket"]
        t0 = time.time()
        for q in QUANTILES:
            m = lgb.LGBMRegressor(objective="quantile", alpha=q, **self.params)
            kw = {}
            if X_val is not None:
                kw = dict(eval_set=[(self._prep(X_val), y_val)], eval_metric="quantile",
                          callbacks=[lgb.early_stopping(self.early_stopping_rounds, verbose=False)])
            m.fit(self._prep(X), y, **kw)
            self.models[q] = m
            log.info("%s %s q=%.2f best_iter=%s", self.name, self.source, q, m.best_iteration_)
        self.meta["train_seconds"] = round(time.time() - t0, 1)
        self.meta["features"] = self.features
        self.meta["params"] = self.params
        return self

    def predict(self, X):
        Xp = self._prep(X)
        q = np.column_stack([self.models[qq].predict(Xp) for qq in QUANTILES])
        q = finalize_quantiles(q, self.capacity_mw, self.night_mask(X))
        return to_qframe(q, X.index)

    def feature_importance(self) -> pd.Series:
        m = self.models[0.5]
        return pd.Series(m.booster_.feature_importance("gain"), index=self.features).sort_values(ascending=False)
