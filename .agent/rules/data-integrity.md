---
trigger: model_decision
description: Apply when touching datasets, features, splits, evaluation, metrics, calibration, or any number shown to judges.
---

# Data integrity & evaluation rules

1. Forecast framing: rows are `(issue_time, target_time, lead_h)`. Weather lead column by lead: 1–24 h → `fx1_*`, 25–48 h → `fx2_*` (`fx0_*` is never used as a lead forecast feature).
2. Generation-history features use observations at or before `issue_time` only.
3. Splits (frozen in `config/site.yaml`): train → validation → test, chronological, 48 h gaps. Tune, ensemble-weight and conformal-calibrate on validation; report on test.
4. Report MAE, RMSE, nMAE, nRMSE, bias, skill vs persistence, pinball, PICP, MPIW — overall and per slice; solar also daylight-only.
5. Combined (solar+wind) bands via copula sampling — never sum quantiles.
6. Real vs simulated: every figure/table states whether it is twin data or real data (R1–R5). Keep `docs/data-assumptions.md` provenance table current.
7. Subsampling backtest origins (e.g. for Chronos-2 speed) must be systematic (every k-th day) and documented.
8. If a result looks too good (e.g. skill > 80% day-ahead), suspect leakage first and check before celebrating.
