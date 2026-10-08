"""Train all models for one source, fit ensemble + CQR, evaluate on val and test, save artifacts.

Validation split usage (test is never touched until the final evaluation):
  val_fit (first 60% of val issue times): early stopping, residual bands, ensemble weights
  val_cal (last 40%)                     : conformal calibration (CQR)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from terra.config import TerraConfig
from terra.eval.backtest import align_external, long_predictions
from terra.eval.metrics import metrics_table
from terra.features.build_features import feature_columns, xy
from terra.logs import get_logger
from terra.models.baselines import Persistence, WeekMean
from terra.models.conformal import CQR
from terra.models.ensemble import Ensemble
from terra.models.gbm import GBMQuantile
from terra.models.physics import Physics
from terra.models.registry import save_object
from terra.paths import ARTIFACTS
from terra.pipelines.bundle import ForecastBundle
from terra.schema import QCOLS

log = get_logger(__name__)


def split_val(frame: pd.DataFrame, frac: float = 0.6) -> pd.DataFrame:
    f = frame.copy()
    val_issues = np.sort(f.loc[f["split"] == "val", "issue_time_utc"].unique())
    if len(val_issues):
        cut = val_issues[int(len(val_issues) * frac)]
        is_val = f["split"] == "val"
        f.loc[is_val & (f["issue_time_utc"] < cut), "split"] = "val_fit"
        f.loc[is_val & (f["issue_time_utc"] >= cut), "split"] = "val_cal"
    return f


def train_source(frame: pd.DataFrame, source: str, cfg: TerraConfig,
                 external: dict[str, pd.DataFrame] | None = None, gbm_params: dict | None = None
                 ) -> tuple[ForecastBundle, pd.DataFrame, pd.DataFrame]:
    """external: optional {name: predictions keyed by issue/target} e.g. {'chronos2_zs': df}."""
    cap = cfg.capacity_mw(source)
    f = split_val(frame)
    Xtr, ytr = xy(f, "train")
    Xvf, yvf = xy(f, "val_fit")
    log.info("%s rows train=%d val_fit=%d val_cal=%d test=%d", source, len(Xtr), len(Xvf),
             (f.split == "val_cal").sum(), (f.split == "test").sum())

    models = {
        "persistence": Persistence(cap, source).fit(Xtr, ytr, Xvf, yvf),
        "week_mean": WeekMean(cap, source).fit(Xtr, ytr, Xvf, yvf),
        "physics": Physics(cap, source).fit(Xtr, ytr, Xvf, yvf),
        "gbm": GBMQuantile(cap, source, gbm_params).fit(Xtr, ytr, Xvf, yvf),
    }
    members = ["physics", "gbm"]
    ext_ok = {}
    for name, ext in (external or {}).items():
        cover = align_external(f[f.split.isin(["val_fit", "val_cal", "test"])], ext)
        if cover.isna().any().any():
            log.warning("%s lacks full val/test coverage -> evaluated but not in ensemble", name)
        else:
            members.append(name)
        ext_ok[name] = ext

    bundle = ForecastBundle(source, cap, models, Ensemble(members), CQR(), feature_columns(f))

    def preds_for(split: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        rows = f[f["split"] == split]
        return rows, bundle.member_predictions(rows, ext_ok)

    rows_vf, p_vf = preds_for("val_fit")
    bundle.ensemble.fit({m: p_vf[m] for m in members}, rows_vf["y"].to_numpy(),
                        rows_vf["lead_bucket"].astype(str).to_numpy())
    rows_vc, p_vc = preds_for("val_cal")
    raw_vc = bundle.ensemble.predict({m: p_vc[m] for m in members}, rows_vc["lead_bucket"].astype(str).to_numpy())
    bundle.cqr.fit(raw_vc, rows_vc["y"].to_numpy(), rows_vc)

    results = []
    for split in ("val_cal", "test"):
        rows = f[f["split"] == split]
        in_ensemble = {n: e for n, e in ext_ok.items() if n in members}
        cal, preds, _ = bundle.predict(rows, in_ensemble)
        for n, e in ext_ok.items():          # also report externals that are not ensemble members
            preds[n] = align_external(rows, e)
        preds["ensemble"] = cal
        lp = long_predictions(rows, preds, source)
        lp["split"] = split
        results.append(lp.dropna(subset=list(QCOLS)))
    preds_long = pd.concat(results, ignore_index=True)
    test = preds_long[preds_long["split"] == "test"]
    table = metrics_table(test, cap)
    bundle.meta = {"config_hash": cfg.hash(), "members": members,
                   "ensemble_weights": bundle.ensemble.weights_table().round(4).to_dict(),
                   "gbm_train_seconds": models["gbm"].meta.get("train_seconds"),
                   "test_metrics": table.round(4).to_dict(orient="records")}
    return bundle, preds_long, table


def train_all(frames: dict[str, pd.DataFrame], cfg: TerraConfig,
              external: dict[str, dict[str, pd.DataFrame]] | None = None, save: bool = True,
              gbm_params: dict[str, dict] | None = None) -> dict:
    """gbm_params: optional {source: LightGBM params} from config/gbm_params.yaml (task T4.5)."""
    out = {}
    for source, frame in frames.items():
        bundle, preds, table = train_source(frame, source, cfg, (external or {}).get(source),
                                            (gbm_params or {}).get(source))
        out[source] = (bundle, preds, table)
        log.info("%s test metrics:\n%s", source, table[["model", "mae", "rmse", "nmae_pct", "picp80",
                                                        "skill_vs_persistence"]].round(3).to_string(index=False))
        if save:
            d = save_object(bundle, source, "bundle", bundle.meta)
            bt = ARTIFACTS / "backtests" / source
            bt.mkdir(parents=True, exist_ok=True)
            preds.to_parquet(bt / "predictions.parquet")
            table.to_csv(bt / "metrics_test.csv", index=False)
            (bt / "meta.json").write_text(json.dumps({"bundle_dir": str(d), **bundle.meta}, indent=2, default=str))
    return out
