"""Time-boxed LightGBM tuning on train holdout (never validation/test). Writes config/gbm_params.yaml.

Protocol (pre-registered):
- Per source (solar, wind) separately.
- Fit on TRAIN split minus last 20% of issue times (temporal holdout 'tune_holdout').
- Drop rows whose target crosses the boundary (issue_time < cut and target_time >= cut).
- Objective: mean pinball loss over the 5 quantiles (0.05, 0.10, 0.50, 0.90, 0.95) on tune_holdout.
- Search space:
    num_leaves: 15-127
    min_child_samples: 20-200
    learning_rate: 0.01-0.08 (log)
    subsample: 0.6-1.0
    colsample_bytree: 0.5-1.0
    reg_lambda: 0.0-10.0
    reg_alpha: 0.0-5.0
- n_estimators up to 3000 with early stopping (100 rounds) on tune_holdout.
- Optuna TPE seed 42, timeout 40 minutes per source (hard cap; total <= 90 minutes).
- Trial 0 enqueued with DEFAULT params so relative improvement is measured against them.
- Adoption rule: adopt tuned params only if relative pinball improvement on tune_holdout >= 1.0%;
  otherwise retain default params and set adopted: false.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
import yaml

from terra.config import load_config
from terra.eval.metrics import pinball_multi
from terra.features.build_features import feature_columns
from terra.logs import get_logger
from terra.models.base import finalize_quantiles
from terra.paths import CONFIG_DIR, DATA_PROCESSED
from terra.pipelines.train import split_train_holdout
from terra.schema import QUANTILES

log = get_logger(__name__)

DEFAULT_PARAMS_TRIAL = {
    "num_leaves": 63,
    "min_child_samples": 50,
    "learning_rate": 0.03,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "reg_alpha": 0.0,
}


def sample_params(trial: optuna.Trial) -> dict:
    return {
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 10.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 5.0),
    }


def evaluate_trial(
    p: dict,
    X_fit: pd.DataFrame,
    y_fit: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    capacity: float,
    source: str,
    night_mask: np.ndarray | None,
) -> float:
    preds = []
    for q in QUANTILES:
        m = lgb.LGBMRegressor(
            objective="quantile",
            alpha=q,
            n_estimators=3000,
            learning_rate=p["learning_rate"],
            num_leaves=p["num_leaves"],
            min_child_samples=p["min_child_samples"],
            subsample=p["subsample"],
            subsample_freq=1,
            colsample_bytree=p["colsample_bytree"],
            reg_lambda=p["reg_lambda"],
            reg_alpha=p["reg_alpha"],
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        m.fit(
            X_fit,
            y_fit,
            eval_set=[(X_val, y_val)],
            eval_metric="quantile",
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        preds.append(m.predict(X_val))

    q_arr = np.column_stack(preds)
    q_fin = finalize_quantiles(q_arr, capacity, night_mask)
    return pinball_multi(y_val.to_numpy(), q_fin, QUANTILES)


def tune_source(
    source: str,
    timeout_s: int = 2400,
    n_trials: int | None = None,
    seed: int = 42,
) -> dict:
    cfg = load_config()
    cap = cfg.capacity_mw(source)
    frame_path = DATA_PROCESSED / f"framed_{source}.parquet"
    if not frame_path.exists():
        raise FileNotFoundError(f"Missing framed dataset {frame_path}. Run 'terra frame' first.")

    raw_frame = pd.read_parquet(frame_path)
    df_fit, df_holdout = split_train_holdout(raw_frame, holdout_frac=0.2)
    feats = feature_columns(raw_frame)

    X_fit = df_fit[feats].astype("float32")
    y_fit = df_fit["y"].astype("float32")
    X_val = df_holdout[feats].astype("float32")
    y_val = df_holdout["y"].astype("float32")
    night = (
        (df_holdout["cal_is_day"].to_numpy() == 0)
        if (source == "solar" and "cal_is_day" in df_holdout)
        else None
    )

    log.info(
        "Tuning %s: fit_rows=%d, holdout_rows=%d, feats=%d, timeout=%ds, seed=%d",
        source,
        len(X_fit),
        len(X_val),
        len(feats),
        timeout_s,
        seed,
    )

    def objective(trial: optuna.Trial) -> float:
        p = sample_params(trial)
        loss = evaluate_trial(p, X_fit, y_fit, X_val, y_val, cap, source, night)
        log.info(
            "[%s Trial %d] pinball=%.5f params=%s",
            source,
            trial.number,
            loss,
            {k: round(v, 4) if isinstance(v, float) else v for k, v in p.items()},
        )
        return loss

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.enqueue_trial(DEFAULT_PARAMS_TRIAL)

    t0 = time.time()
    study.optimize(objective, n_trials=n_trials, timeout=timeout_s)
    wall_clock_s = time.time() - t0
    wall_clock_min = wall_clock_s / 60.0

    trial_0 = study.trials[0]
    default_pinball = float(trial_0.value) if trial_0.value is not None else float("nan")
    best_pinball = float(study.best_value)
    rel_improvement = (
        (default_pinball - best_pinball) / default_pinball
        if default_pinball > 0
        else 0.0
    )

    adopted = rel_improvement >= 0.01

    if adopted:
        chosen_params = {
            k: (int(v) if k in ("num_leaves", "min_child_samples") else float(round(v, 5)))
            for k, v in study.best_params.items()
        }
    else:
        chosen_params = {
            k: (int(v) if k in ("num_leaves", "min_child_samples") else float(round(v, 5)))
            for k, v in DEFAULT_PARAMS_TRIAL.items()
        }

    log.info(
        "%s tuning finished in %.1f min (%d trials). Default pinball=%.5f, Best pinball=%.5f, "
        "Rel improvement=%.2f%%. Adopted: %s",
        source,
        wall_clock_min,
        len(study.trials),
        default_pinball,
        best_pinball,
        rel_improvement * 100.0,
        adopted,
    )

    return {
        "adopted": bool(adopted),
        "tuned_on": "tune_holdout",
        "objective": "mean_pinball_5q",
        "default_pinball": float(round(default_pinball, 5)),
        "best_pinball": float(round(best_pinball, 5)),
        "relative_improvement": float(round(rel_improvement, 5)),
        "n_trials": int(len(study.trials)),
        "seed": int(seed),
        "wall_clock_minutes": float(round(wall_clock_min, 2)),
        "params": chosen_params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune LightGBM hyperparameters on train holdout")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["solar", "wind"],
        choices=["solar", "wind"],
        help="Sources to tune",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=2400,
        help="Timeout in seconds per source (default: 2400 = 40m)",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=None,
        help="Max trials per source (default: None, time-capped)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Optuna TPE sampler seed (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CONFIG_DIR / "gbm_params.yaml",
        help="Output YAML path",
    )
    args = parser.parse_args()

    results: dict[str, dict] = {}
    if args.output.exists():
        try:
            results = yaml.safe_load(args.output.read_text()) or {}
        except Exception:
            results = {}

    for s in args.sources:
        print(f"\n==================== Tuning {s.upper()} ====================")
        res = tune_source(s, timeout_s=args.timeout, n_trials=args.n_trials, seed=args.seed)
        results[s] = res

    args.output.write_text(yaml.safe_dump(results, sort_keys=False))
    print(f"\nWrote results to {args.output}")


if __name__ == "__main__":
    main()
