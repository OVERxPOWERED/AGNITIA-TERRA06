---
description: Run the evaluation harness and regenerate result tables/plots.
---

# Run a backtest

1. Ensure `data/processed/dataset.parquet` and needed artifacts exist (`make data train`).
2. `make backtest` (all models) or `make backtest MODEL=<name> SPLIT=val|test`.
3. Outputs: `artifacts/backtests/<run_id>/predictions.parquet`, `metrics.json`, plots in `docs/images/`.
4. Regenerate docs: `make report` → `docs/accuracy-report.md`.
5. Sanity checks: persistence skill = 0 by definition; solar night error ≈ 0; PICP near nominal on test after CQR; no suspiciously high skill (leakage check).
6. Only test-split numbers go into the report/pitch.
