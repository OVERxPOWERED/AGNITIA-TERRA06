import numpy as np

from terra.features.build_features import xy
from terra.models.baselines import Persistence
from terra.models.gbm import GBMQuantile
from terra.models.physics import Physics
from terra.schema import QCOLS


def _check_q(q, cap):
    a = q[list(QCOLS)].to_numpy()
    assert (np.diff(a, axis=1) >= -1e-9).all()
    assert a.min() >= 0 and a.max() <= cap + 1e-9


def test_models_quantiles_valid(cfg, frames, tmp_path):
    f = frames["solar"]
    Xtr, ytr = xy(f, "train")
    Xva, yva = xy(f, "val")
    cap = cfg.capacity_mw("solar")
    for m in (Persistence(cap, "solar"), Physics(cap, "solar"),
              GBMQuantile(cap, "solar", {"n_estimators": 60})):
        m.fit(Xtr, ytr, Xva, yva)
        q = m.predict(Xva)
        _check_q(q, cap)
        night = Xva["cal_is_day"].to_numpy() == 0
        assert (q.loc[night, "q95"] == 0).all()
    d = m.save(tmp_path / "gbm")
    again = GBMQuantile.load(d)
    assert np.allclose(again.predict(Xva)["q50"], q["q50"])
