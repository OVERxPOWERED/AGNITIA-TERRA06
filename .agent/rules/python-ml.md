---
trigger: glob
globs: ml/**/*.py, notebooks/**
description: Python, data and ML coding standards for the ml/terra package.
---

# Python / ML rules

## Style
- Python 3.11, type hints on public functions, `ruff` clean (line length 125), docstrings with units.
- Pure functions where possible; I/O at the edges (`pipelines/`, `data/openmeteo.py`).
- Use `pathlib` and `terra.paths` constants; never hard-code absolute paths.
- Logging via `terra.logs.get_logger(__name__)`; no `print` in package code.
- Config via `terra.config.load()`; pass config objects, don't re-read YAML deep inside functions.

## Data
- DataFrames indexed by tz-aware UTC `DatetimeIndex` named `ts_utc`, hourly frequency, sorted, unique.
- Column names follow `.agent/context/data-contracts.md`. Add new columns there first.
- Parquet (pyarrow) for all tabular artifacts; never CSV for internal data (CSV only for user exports).
- Cache external API responses under `data/raw/`; code must run offline after first fetch.

## Modelling
- All models subclass `terra.models.base.ForecastModel` (`fit(X, y, X_val, y_val)`, `predict(X)` → DataFrame `q05,q10,q50,q90,q95`, `save`, `load`).
- Quantiles must be monotone and clipped to `[0, capacity]`; solar is 0 when sun elevation < 0.
- Evaluate only via `terra.eval.backtest`; slices: lead bucket (1–24, 25–48), hour, month, daylight.
- Seed everything (`numpy`, `lightgbm`, `torch`); record seeds in `meta.json`.
- Every artifact gets `meta.json`: model name/version, config hash, git SHA, data span, features, metrics, train time, library versions.
- Never touch the test split during tuning/ensemble weighting/conformal fitting (those use validation).

## Tests
- `pytest`; fixtures from `data/samples/` (tiny). Mark network/large tests `@pytest.mark.slow`.
- Required tests: leakage (framing), metric correctness (hand-computed), twin physics sanity (night=0, ≤ capacity, cut-in/out), engine constraints (dispatch feasibility, monotonic what-if), energy conservation (15-min downscaler).

## Notebooks
- Exploration only. Anything reused moves into `ml/terra/`. Clear large outputs before committing.
