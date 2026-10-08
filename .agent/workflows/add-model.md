---
description: Add a new forecasting model that plugs into the backtest harness, ensemble and API.
---

# Add a model

1. Create `ml/terra/models/<name>.py` implementing `ForecastModel` from `models/base.py`:
   - `name: str` (snake_case, unique; register in `models/__init__.py`)
   - `fit(X_train, y_train, X_val=None, y_val=None) -> self`
   - `predict(X) -> pd.DataFrame` with columns `q05,q10,q50,q90,q95`, same index as X, monotone, clipped `[0, capacity]`
   - `save(dir)` / `load(dir)` writing `meta.json`
2. Use only features allowed by `rules/data-integrity.md`.
3. Add unit tests: shapes, monotone quantiles, clipping, save/load round trip on `data/samples/`.
4. Run `make backtest MODEL=<name>`; compare against persistence and current best in the generated table.
5. If it improves validation pinball/MAE, add it to the ensemble candidate list in config.
6. Document in `docs/model-card.md` (inputs, training cost, results).
