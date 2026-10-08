"""Time-boxed LightGBM tuning on val_fit (never test). Writes config/gbm_params.yaml."""
import lightgbm as lgb
import optuna
import pandas as pd
import yaml

from terra.eval.metrics import mae
from terra.features.build_features import xy
from terra.paths import CONFIG_DIR, DATA_PROCESSED
from terra.pipelines.train import split_val

N_TRIALS, TIMEOUT_S = 40, 1800          # per source; ~30 min max each
best = {}
for s in ("solar", "wind"):
    f = split_val(pd.read_parquet(DATA_PROCESSED / f"framed_{s}.parquet"))
    Xtr, ytr = xy(f, "train")
    Xv, yv = xy(f, "val_fit")
    Xtr, Xv = Xtr.drop(columns="lead_bucket"), Xv.drop(columns="lead_bucket")

    def objective(trial: optuna.Trial) -> float:
        p = {"num_leaves": trial.suggest_int("num_leaves", 15, 255, log=True),
             "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
             "min_child_samples": trial.suggest_int("min_child_samples", 10, 200, log=True),
             "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
             "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True)}
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=2000, subsample=0.8, subsample_freq=1,
                              verbose=-1, **p)
        m.fit(Xtr, ytr, eval_set=[(Xv, yv)], callbacks=[lgb.early_stopping(100, verbose=False)])
        return mae(yv.to_numpy(), m.predict(Xv))

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=N_TRIALS, timeout=TIMEOUT_S)
    best[s] = study.best_params
    print(s, round(study.best_value, 3), study.best_params)
(CONFIG_DIR / "gbm_params.yaml").write_text(yaml.safe_dump(best))
