# TERRA: Hybrid Solar & Wind Forecasting Platform

## 1. Problem & Site
Grid operators and renewable energy providers face significant challenges in forecasting generation due to weather variability. In Madhya Pradesh, regulations (CERC DSM) impose strict penalties for deviating from scheduled generation: ±5% for solar and ±10% for wind (effective April 2026). TERRA addresses this by providing high-accuracy forecasts for a virtual 90 MW hybrid plant (50 MW Wind, 40 MW Solar) located in Dewas, MP.

## 2. Data
The platform uses a simulated digital twin powered by pvlib and windpowerlib using real weather data from the Open-Meteo API. To ensure realism, the digital twin incorporates calibrated noise, soiling, and outage heuristics derived from real Kaggle datasets and Indian SCADA data.

## 3. Method
We generate features from Open-Meteo forecasts and employ a multi-model approach:
- Persistence and Physics baselines
- LightGBM-Quantile models
An ensemble model combines these using Conformalized Quantile Regression (CQR) to produce a reliable 80% and 90% confidence band.

## 4. Results
On the held-out test split, our ensemble model achieved:
- **Solar**: MAE of 0.66 MW (71.4% skill over persistence), 80% band coverage = 91.9%.
- **Wind**: MAE of 4.16 MW (63.6% skill over persistence), 80% band coverage = 85.5%.

## 5. Hero Features & Impact
- **Trust Score**: Evaluates forecast reliability. Strong rank correlation with actual errors (-0.64).
- **Battery Dispatch Advisor**: A linear programming solver that optimizes battery usage to minimize curtailment and fossil backup.
- **Deviation Shield**: Simulates DSM penalties, optimizing schedules to save up to ?3.18 Crores annually.
- **Environmental Impact**: Avoided 2,538.7 MWh of fossil backup and 1,789.8 tCO2 over the test period.

## 6. Architecture
![Architecture](../images/architecture.png)

## 7. Limitations & Future Work
- The current DSM calculation uses illustrative rates due to pending CERC clarifications.
- Live deployment requires transitioning to a commercial weather data license.
- Future work includes integrating real-time SCADA feeds and Day-Ahead Market (DAM) prices for revenue arbitrage.
