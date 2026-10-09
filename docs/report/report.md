# TERRA: Hybrid Solar & Wind Forecasting Platform

## 1. Problem & Site
Grid operators and renewable energy providers in India face tightening regulatory oversight. In Madhya Pradesh, the CERC DSM Regulations (effective from April 1, 2026; illustrative framework, verify before external use) enforce strict tolerance bands around scheduled generation: ±5% for solar and ±10% for wind. Generation deviations beyond these bands incur steep financial penalties and force grid operators to ramp up carbon-heavy fossil backup power.

TERRA addresses this by providing 1–48 h ahead generation forecasts, calibrated uncertainty bands, battery dispatch optimization, and automated deviation charge risk mitigation for a virtual 90 MW hybrid plant (40 MW AC / 50 MW DC Solar + 50 MW Wind) co-located at the Jamgudrani hills ridge in the Dewas wind belt near Indore, MP (22.96° N, 76.05° E, 536 m altitude).

## 2. Data & Provenance
- **Real Weather Data**: Historical actual weather and historical forecasts are retrieved directly from the Open-Meteo API (`ecmwf_ifs025` model, CC BY 4.0).
- **Calibrated Digital Twin**: Plant generation is simulated via a physical digital twin combining `pvlib` (Ineichen clear-sky, Sandia array, PVWatts system loss) and `windpowerlib` (MM100/2000 turbines, Hellmann shear exponent, wake and electrical losses). A realism layer (AR(1) noise, temperature coefficients, soiling accumulation, and stochastic outages) is calibrated against real Indian solar plant data (Kaggle R1), wind turbine SCADA (R2), and official CEA Madhya Pradesh monthly statistics (R4). *The plant is a virtual digital twin at a real location, not an actual operator's private telemetry.*
- **Strict Leak-Free Lead Mapping**: Following ADR-009, forecast weather features are strictly mapped to prevent look-ahead bias: leads 1–24 use 24 h-old forecasts (`fx1_`), and leads 25–48 use 48 h-old forecasts (`fx2_`). Forecasts issued after issue time (`fx0_`) are never used as lead-resolved features.
- **Offline Test Fixture**: `data/samples/dataset_sample.parquet` is an offline synthetic fixture used for automated test suites, not real data.

## 3. Method
The ML pipeline generates 34 leak-free features across forecast weather (`fx_`), physics priors (`phys_mw`), calendar geometry (`cal_`), and pre-issue generation history (`hist_`).
- **Baseline Models**: 24-h Persistence, 7-day Week-Mean, and Physics Digital Twin (`pvlib` / `windpowerlib`).
- **ML Models**: LightGBM Quantile regression models trained on 5 quantiles (`q05`, `q10`, `q50`, `q90`, `q95`) across solar and wind, tuned with Optuna on a temporal hold-out inside the training data (ADR-015; adopted for both sources by a pre-registered relative pinball improvement >= 1.0% rule).
- **Foundation Benchmark**: Amazon Chronos-2 zero-shot model (`chronos2_zs`) with leak-free weather covariates, evaluated on Kaggle 2× Tesla T4 GPUs (ADR-014, ADR-016; comparison-only benchmark to eliminate runtime PyTorch dependencies for serving).
- **Ensemble & CQR**: A lead-dependent weighted average combines the physics prior and LightGBM model, followed by Conformalized Quantile Regression (CQR) to calibrate 80% and 90% uncertainty intervals (this is the production model served by the API and dashboard).

## 4. Results (Held-Out Test Split)
Evaluated over 179 held-out test days (2026-04-03 to 2026-09-28, 34,192 row-hours) under strict leak-free lead mapping. Six models are compared on the test split per source. All metrics are produced by the evaluation harness (`docs/accuracy-report.md`):

### Solar (40 MW AC Capacity)
| Model | MAE (MW) | RMSE (MW) | nMAE (%) | Bias (MW) | Skill vs Persistence | 80% Coverage (PICP80) | 90% Coverage (PICP90) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ensemble (served) | 1.57 | 3.20 | 3.9% | -0.14 | **+27.8%** | 91.8% | 96.5% |
| LightGBM (tuned) | 1.57 | 3.20 | 3.9% | -0.14 | +27.8% | 86.2% | 91.6% |
| Chronos-2 ZS (benchmark) | 1.68 | 3.48 | 4.2% | +0.27 | +22.5% | 89.4% | 94.9% |
| Week-Mean | 1.83 | 3.77 | 4.6% | -0.01 | +15.5% | 81.6% | 87.7% |
| Physics Twin | 2.12 | 4.03 | 5.3% | -0.19 | +2.3% | 82.9% | 87.0% |
| Persistence | 2.17 | 4.54 | 5.4% | -0.01 | 0.0% | 81.7% | 87.2% |

- **Daylight Hours Only (Solar)**: Ensemble MAE is 2.91 MW (7.3% nMAE, RMSE 4.36 MW), beating persistence (4.03 MW MAE, 10.1% nMAE) by **+27.8% skill**. Standalone tuned LightGBM achieves identical daylight MAE (2.91 MW, 7.3% nMAE, RMSE 4.36 MW). Chronos-2 zero-shot achieves 3.12 MW MAE (7.8% nMAE, RMSE 4.74 MW, +22.5% skill).
- **Daylight Uncertainty Coverage**: Solar daylight PICP80 is 84.8% and PICP90 is 93.6% for Ensemble (Tuned GBM: 74.4% PICP80, 84.5% PICP90; Chronos-2: 80.3% PICP80, 90.6% PICP90). All-hours coverage (91.8% / 96.5%) is higher because nighttime hours have zero solar generation and narrow zero-variance bands.

### Wind (50 MW Capacity)
| Model | MAE (MW) | RMSE (MW) | nMAE (%) | Bias (MW) | Skill vs Persistence | 80% Coverage (PICP80) | 90% Coverage (PICP90) |
|---|---:|---:|---:|---:|---:|---:|---:|
| LightGBM (tuned) | 3.99 | 5.96 | 8.0% | -0.92 | **+38.3%** | 76.8%* | 88.1%* |
| Chronos-2 ZS (benchmark) | 4.05 | 5.94 | 8.1% | -0.09 | +37.4% | 74.6%* | 86.5%* |
| Ensemble (served) | 4.15 | 6.10 | 8.3% | -0.33 | +35.8% | 72.6%* | 86.1%* |
| Physics Twin | 5.26 | 7.55 | 10.5% | +1.00 | +18.6% | 38.6% | 49.4% |
| Week-Mean | 6.37 | 8.90 | 12.7% | -0.07 | +1.6% | 43.1% | 55.5% |
| Persistence | 6.47 | 9.52 | 12.9% | +0.04 | 0.0% | 52.0% | 63.9% |

*\*See Limitations regarding wind ensemble weights and monsoon coverage shift.*

### Lead-Bucket Performance
- **Solar**:
  - Leads 1–24 (Day 1): Ensemble MAE 1.51 MW (3.8% nMAE, skill +26.7%); Tuned GBM MAE 1.51 MW (3.8% nMAE); Chronos-2 MAE 1.60 MW (4.0% nMAE).
  - Leads 25–48 (Day 2): Ensemble MAE 1.62 MW (4.0% nMAE, skill +28.9%); Tuned GBM MAE 1.62 MW (4.0% nMAE); Chronos-2 MAE 1.77 MW (4.4% nMAE).
- **Wind**:
  - Leads 1–24 (Day 1): Chronos-2 MAE 3.74 MW (7.5% nMAE, skill +37.7%); Tuned GBM MAE 3.81 MW (7.6% nMAE, skill +36.5%); Ensemble MAE 3.92 MW (7.8% nMAE, skill +34.8%).
  - Leads 25–48 (Day 2): Tuned GBM MAE 4.17 MW (8.3% nMAE, skill +40.0%); Chronos-2 MAE 4.36 MW (8.7% nMAE, skill +37.1%); Ensemble MAE 4.39 MW (8.8% nMAE, skill +36.7%).

## 5. Hero Features & Impact
All figures are produced by the evaluation harness (`docs/engine-results.md`, `artifacts/evaluation/results.json`):

- **Trust Score (H3)**: Evaluates forecast confidence before generation occurs. Spearman rank correlation with actual absolute error is **-0.665 for solar** and **-0.518 for wind**. MAE monotonically drops from Low Trust (solar 3.94 MW, wind 5.57 MW) to Medium Trust (solar 1.18 MW, wind 2.52 MW) to High Trust (solar 0.33 MW, wind 1.23 MW).
- **Battery Dispatch Advisor (H2)**: A Linear Programming solver schedules the co-located 25 MW / 50 MWh BESS to satisfy a contracted 30 MW peak demand profile. Over the 179-day test period, ensemble-guided dispatch:
  - Avoids **304.7 MWh of fossil backup** (47,683.8 MWh vs 47,988.4 MWh under persistence) and avoids **248.9 MWh of curtailment** (7,390.1 MWh vs 7,639.0 MWh).
  - Compared to a counterfactual with no battery (48,634.5 MWh backup), the system avoids **950.7 MWh of fossil backup**.
  - Saves **₹29,90,857 (~₹29.91 Lakhs)** in backup and operating costs over 179 days (₹43,65,43,963 vs ₹43,95,34,820).
- **Deviation Shield (H5)**: Simulates CERC DSM penalty schedules under illustrative regulatory rates (`verify: true`). Over the 179-day test split, TERRA saves **₹1,11,45,303 (~₹1.11 Crores / ₹111.45 Lakhs)** in deviation penalties against persistence scheduling:
  - Solar penalties reduced from ₹53.66 Lakhs (persistence) to ₹27.29 Lakhs (terra_p50) and ₹26.65 Lakhs (terra_optimized).
  - Wind penalties reduced from ₹1.28 Crores / ₹1,27,98,400 (persistence) to ₹43.00 Lakhs (terra_p50) and ₹43.53 Lakhs (terra_optimized).
- **Environmental Impact**: Avoided fossil backup directly prevents **214.8 tCO2** in greenhouse emissions (CEA CO2 Baseline Database v22.0 combined margin factor: 0.705 tCO2/MWh, FY2025-26).
- **Data-Driven Alerts**: Thresholds learned strictly from training split quantiles (ADR-010: Solar low 2.11 MW daylight, high 28.95 MW; Wind low 1.14 MW, high 18.21 MW; Hybrid low 1.68 MW, high 31.70 MW). Test split evaluation deduplicated across daily 00:00 UTC runs achieves:
  - Solar LOW: 99.5% precision, 79.3% recall (200 alert hours / 251 event hours).
  - Solar HIGH: 77.5% precision, 18.6% recall (80 alert hours / 333 event hours).
  - Wind LOW: 75.3% precision, 21.8% recall (162 alert hours / 559 event hours).
  - Wind HIGH: 74.6% precision, 36.6% recall (331 alert hours / 675 event hours).
  - Hybrid LOW: 70.8% precision, 22.1% recall (72 alert hours / 231 event hours).
  - Hybrid HIGH: 84.8% precision, 45.3% recall (374 alert hours / 700 event hours).

## 6. Architecture & UI
TERRA provides 10 purpose-built Next.js pages: Overview (`/`), Forecast (`/forecast`), Models (`/models`), Alerts (`/alerts`), Dispatch (`/dispatch`), What-If (`/whatif`), Deviation Shield (`/deviation`), Impact (`/impact`), Trust (`/trust`), and Assumptions (`/assumptions`). Alerts are populated by `ForecastJob` in `backend/app/scheduler.py` into SQLite and pushed live via Server-Sent Events (`/alerts/stream`). Both `/forecast` and `/models` allow inspecting all compared models, including the `chronos2_zs` benchmark.

![Architecture](../images/architecture.png)

## 7. Limitations and Honesty Notes
1. **Virtual Plant Provenance**: Plant generation is simulated by a calibrated digital twin at a real geographic site (Dewas, MP). While physical and statistical parameters are calibrated on real Indian operational datasets, the hourly series does not represent private utility SCADA data.
2. **Real Weather vs. Synthetic Baselines**: Earlier preliminary documents were generated on synthetic weather without strict lead isolation, reporting overly optimistic metrics (e.g. 71% solar skill). Real leak-free evaluation under strict 24 h / 48 h lead mapping yields lower, physically honest skill (+27.8% for solar ensemble, +35.8% for wind ensemble, +38.3% for tuned wind LightGBM).
3. **Uncertainty Band Calibration & Seasonal Shift**: Nominal 80% and 90% bands hold well for solar daylight hours (84.8% PICP80, 93.6% PICP90; all-hours numbers of 91.8% / 96.5% are inflated by zero-generation nights). However, wind coverage is below nominal (72.6% PICP80 for ensemble, 76.8% for tuned LightGBM; 86.1% / 88.1% PICP90). This occurs because conformal quantile calibration was fitted on the dry winter validation window (October 2025 – March 2026), whereas the held-out test split is monsoon-heavy (April – September 2026) with significantly higher wind speeds and volatility.
4. **Tuning Impact & Wind Ensemble Transfer Discrepancy**: Optuna hyperparameter tuning on a temporal holdout inside the training data improved solar GBM MAE and ensemble MAE by ~2.3-2.4% (from 1.60 MW to 1.57 MW). On wind, tuning improved standalone GBM MAE by ~0.4% (from 4.01 MW to 3.99 MW) and widened its 80% coverage by ~5.6 points (from 72.7% to 76.8%). However, the wind ENSEMBLE got slightly worse on test (+1.5% MAE, from 4.09 MW to 4.15 MW; RMSE from 6.02 MW to 6.10 MW) because its physics/gbm blend weights (0.35 physics / 0.65 gbm for leads 1–24) were fitted on the dry winter validation window and do not transfer cleanly to the monsoon-heavy test window where wind physics prior error characteristics change. Standalone tuned LightGBM (3.99 MW) and Chronos-2 zero-shot (4.05 MW) both beat the wind ensemble on test, and Chronos-2 achieved the lowest wind RMSE overall (5.94 MW). We state this plainly without artificially re-tuning on test outcomes; re-fitting blend weights with seasonal validation is recorded as future work.
5. **Chronos-2 as Comparison-Only Benchmark**: Amazon Chronos-2 zero-shot foundation model was evaluated on Kaggle GPUs with leak-free weather covariates. While highly competitive (beating the wind ensemble in MAE and achieving lowest wind RMSE of 5.94 MW), it is kept as an external benchmark rather than an ensemble member to avoid multi-GB PyTorch runtime overhead on serverless API containers.
6. **Regulatory and Cost Numbers**: DSM deviation penalty rates and pricing hypotheses are illustrative and marked `verify: true` in configuration. They must be verified against applicable state and central grid codes prior to commercial deployment.
7. **Deployment Status**: Deployment is currently deferred per project rules; deployment configurations (Docker / Render / Vercel) exist solely as configuration templates.
