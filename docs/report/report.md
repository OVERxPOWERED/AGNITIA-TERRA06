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
- **Baseline Models**: 24-h Persistence, Physics Digital Twin, and 7-day Week-Mean.
- **ML Models**: LightGBM Quantile regression models trained on 5 quantiles (`q05`, `q10`, `q50`, `q90`, `q95`) across solar and wind, with Chronos-2 zero-shot fallback.
- **Ensemble & CQR**: A lead-dependent weighted average combines the physics prior and LightGBM model, followed by Conformalized Quantile Regression (CQR) to calibrate 80% and 90% uncertainty intervals.

## 4. Results (Held-Out Test Split)
Evaluated over 179 held-out test days (2026-04-03 to 2026-09-28, 34,192 row-hours) under strict leak-free lead mapping. All metrics are produced by the evaluation harness (`docs/accuracy-report.md`):

### Solar (40 MW AC Capacity)
| Model | MAE (MW) | RMSE (MW) | nMAE (%) | Bias (MW) | Skill vs Persistence | 80% Coverage (PICP80) | 90% Coverage (PICP90) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ensemble | 1.60 | 3.27 | 4.01% | -0.36 | **+26.1%** | 92.2% | 96.2% |
| LightGBM | 1.60 | 3.27 | 4.01% | -0.37 | +26.1% | 83.5% | 90.3% |
| Persistence | 2.17 | 4.54 | 5.43% | -0.01 | 0.0% | 81.7% | 87.2% |
| Physics Twin | 2.12 | 4.03 | 5.30% | -0.19 | +2.3% | 82.9% | 87.0% |

- **Daylight Hours Only (Solar)**: Ensemble MAE is 2.97 MW (7.43% nMAE, RMSE 4.46 MW), beating persistence (4.03 MW MAE, 10.06% nMAE) by **+26.1% skill**.
- **Daylight Uncertainty Coverage**: Solar daylight PICP80 is 85.4% and PICP90 is 93.0% (all-hours coverage is inflated by nighttime zero-generation hours).

### Wind (50 MW Capacity)
| Model | MAE (MW) | RMSE (MW) | nMAE (%) | Bias (MW) | Skill vs Persistence | 80% Coverage (PICP80) | 90% Coverage (PICP90) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ensemble | 4.09 | 6.02 | 8.19% | -0.42 | **+36.7%** | 73.2%* | 86.3%* |
| LightGBM | 4.01 | 5.96 | 8.01% | -0.92 | +38.1% | 72.7% | 83.1% |
| Persistence | 6.47 | 9.52 | 12.94% | +0.04 | 0.0% | 52.0% | 63.9% |
| Physics Twin | 5.26 | 7.55 | 10.53% | +1.00 | +18.6% | 38.6% | 49.4% |

*\*See Limitations regarding wind coverage under monsoon conditions.*

### Lead-Bucket Performance
- **Solar**: Leads 1–24 (Day 1): MAE 1.55 MW (3.87% nMAE, skill 25.0%); Leads 25–48 (Day 2): MAE 1.66 MW (4.15% nMAE, skill 27.2%).
- **Wind**: Leads 1–24 (Day 1): MAE 3.84 MW (7.68% nMAE, skill 36.0%); Leads 25–48 (Day 2): MAE 4.35 MW (8.70% nMAE, skill 37.4%).

## 5. Hero Features & Impact
All figures are produced by the evaluation harness (`docs/engine-results.md`, `artifacts/evaluation/results.json`):

- **Trust Score (H3)**: Evaluates forecast confidence before generation occurs. Spearman rank correlation with actual absolute error is **-0.671 for solar** and **-0.503 for wind**. MAE monotonically drops from Low Trust (solar 3.95 MW, wind 5.45 MW) to High Trust (solar 0.18 MW, wind 1.27 MW).
- **Battery Dispatch Advisor (H2)**: A Linear Programming solver schedules the co-located 25 MW / 50 MWh BESS to satisfy a contracted 30 MW peak demand profile. Over the 179-day test period, ensemble-guided dispatch:
  - Avoids **261.2 MWh of fossil backup** (47,727.2 MWh vs 47,988.4 MWh under persistence) and avoids **170.3 MWh of curtailment**.
  - Compared to a counterfactual with no battery (48,634.5 MWh backup), the system avoids **907.3 MWh of fossil backup**.
  - Saves **₹25,21,213 (~₹25.21 Lakhs)** in backup and operating costs.
- **Deviation Shield (H5)**: Simulates CERC DSM penalty schedules under illustrative regulatory rates (`verify: true`). Over the 179-day test split, TERRA saves **₹1,12,58,024 (~₹1.13 Crores)** in deviation penalties against persistence scheduling (Solar penalties reduced from ₹53.66 Lakhs to ₹27.16 Lakhs; Wind penalties reduced from ₹1.28 Crores to ₹41.47 Lakhs).
- **Environmental Impact**: Avoided fossil backup directly prevents **184.2 tCO2** in greenhouse emissions (CEA CO2 Baseline Database v22.0 combined margin factor: 0.705 tCO2/MWh, FY2025-26).
- **Data-Driven Alerts**: Thresholds learned strictly from training split quantiles (ADR-010: Solar low 2.11 MW daylight, high 28.95 MW; Wind low 1.14 MW, high 18.21 MW; Hybrid low 1.68 MW, high 31.70 MW). Test split precision reaches 99.5% for solar low-generation alerts and 87.4% for hybrid high-generation alerts.

## 6. Architecture & UI
TERRA provides 10 purpose-built Next.js pages: Overview (`/`), Forecast (`/forecast`), Models (`/models`), Alerts (`/alerts`), Dispatch (`/dispatch`), What-If (`/whatif`), Deviation Shield (`/deviation`), Impact (`/impact`), Trust (`/trust`), and Assumptions (`/assumptions`). Alerts are populated by `ForecastJob` in `backend/app/scheduler.py` into SQLite and pushed live via Server-Sent Events (`/alerts/stream`).

![Architecture](../images/architecture.png)

## 7. Limitations and Honesty Notes
1. **Virtual Plant Provenance**: Plant generation is simulated by a calibrated digital twin at a real geographic site (Dewas, MP). While physical and statistical parameters are calibrated on real Indian operational datasets, the hourly series does not represent private utility SCADA data.
2. **Real Weather vs. Synthetic Baselines**: Earlier preliminary documents were generated on synthetic weather without strict lead isolation, reporting overly optimistic metrics (e.g. 71% solar skill). Real leak-free evaluation under strict 24 h / 48 h lead mapping yields lower, physically honest skill (+26.1% for solar, +36.7% for wind).
3. **Uncertainty Band Calibration & Seasonal Shift**: Nominal 80% and 90% bands hold well for solar daylight hours (85.4% PICP80, 93.0% PICP90; all-hours numbers of 92.2% / 96.2% are inflated by zero-generation nights). However, wind coverage is below nominal (73.2% PICP80, 86.3% PICP90). This occurs because conformal quantile calibration was fitted on the dry winter validation window (October 2025 – March 2026), whereas the held-out test split is monsoon-heavy (April – September 2026) with significantly higher wind speeds and volatility.
4. **Regulatory and Cost Numbers**: DSM deviation penalty rates and pricing hypotheses are illustrative and marked `verify: true` in configuration. They must be verified against applicable state and central grid codes prior to commercial deployment.
5. **Deployment Status**: Deployment is currently deferred per project rules; deployment configurations (Docker / Render / Vercel) exist solely as configuration templates.
