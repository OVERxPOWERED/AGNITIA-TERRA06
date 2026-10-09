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


def test_external_comparison_only_default(cfg, frames):
    from terra.pipelines.train import train_source
    f = frames["solar"]
    keys = f[["issue_time_utc", "target_time_utc"]].drop_duplicates()
    ext_df = keys.copy()
    for q in QCOLS:
        ext_df[q] = 1.0

    # 1. By default: external with full coverage is reported but NOT in ensemble
    bundle, preds_long, table = train_source(
        f, "solar", cfg, external={"mock_ext": ext_df},
        gbm_params={"n_estimators": 5}, chronos_in_ensemble=False
    )
    assert "mock_ext" not in bundle.ensemble.members
    assert set(bundle.ensemble.members) == {"physics", "gbm"}
    assert "mock_ext" in table["model"].values
    assert "mock_ext" in preds_long["model"].values

    # 2. When chronos_in_ensemble=True: joins ensemble
    bundle_ens, _, _ = train_source(
        f, "solar", cfg, external={"mock_ext": ext_df},
        gbm_params={"n_estimators": 5}, chronos_in_ensemble=True
    )
    assert "mock_ext" in bundle_ens.ensemble.members

