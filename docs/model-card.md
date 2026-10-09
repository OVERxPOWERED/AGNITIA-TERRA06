# Model Card — TERRA Forecasting Models

**Plant**: Virtual co-located solar + wind plant, Dewas wind belt, Madhya Pradesh, India  
**Capacity**: 40 MW solar (AC) + 50 MW wind = 90 MW total (50 MW DC solar)  
**Data**: Digital twin generated from real Open-Meteo weather, calibrated on real Indian plant data (Phase 2)  
**Horizon**: 1–48 h ahead, issued at 00:00 / 12:00 UTC  
**Targets**: `solar_mw` (AC generation), `wind_mw` (net-of-wake output)  

> [!IMPORTANT]
> Generation is **simulated** by a calibrated digital twin at a real location. All metrics are on held-out test data (time-based split, no shuffle). No actual operator data.

---

## Feature Set (34 features, same for solar and wind)

### `fx_` — Forecast weather (16 features)
Feature-lead matching: leads 1–24 → `fx1_`, leads 25–48 → `fx2_` (day-ahead / two-day-ahead; `fx0_` is never used as a lead forecast feature)

| Feature | Meaning |
|---|---|
| `fx_ghi` | Global horizontal irradiance, W/m² (ECMWF IFS 025) |
| `fx_dni` | Direct normal irradiance, W/m² |
| `fx_dhi` | Diffuse horizontal irradiance, W/m² |
| `fx_cloud` | Cloud cover, % |
| `fx_t2m` | 2 m air temperature, °C |
| `fx_rh2m` | 2 m relative humidity, % |
| `fx_psfc` | Surface pressure, hPa |
| `fx_ws10` | 10 m wind speed, m/s |
| `fx_ws100` | 100 m wind speed, m/s |
| `fx_wd100_sin` | Wind direction sine component (100 m) |
| `fx_wd100_cos` | Wind direction cosine component (100 m) |
| `fx_rho` | Air density, kg/m³ (derived from t2m + psfc) |
| `fx_shear` | Wind shear exponent (log of ws100/ws10 ratio) |
| `fx_precip` | Precipitation, mm/h |
| `fx_csi` | Clear-sky index = ghi / cs_ghi (clipped 0–1.5) |
| `fx_ws100_cubed` | Wind speed cubed (100 m) — linear proxy for power |

### `phys_mw` — Physics twin prediction (1 feature)
Digital twin output (pvlib solar + MM100/2000 power curve) applied to forecast weather. Provides a physically-grounded prior.

### `cal_` — Calendar & solar geometry (8 features)

| Feature | Meaning |
|---|---|
| `cal_hour_sin` / `cal_hour_cos` | IST hour encoded as circular sine/cosine |
| `cal_doy_sin` / `cal_doy_cos` | Day-of-year encoded as circular sine/cosine |
| `cal_weekday` | Integer weekday (0 = Monday, 6 = Sunday) |
| `cal_cs_ghi` | Clear-sky GHI (pvlib Ineichen), W/m² |
| `cal_zenith` | Solar zenith angle, degrees |
| `cal_is_day` | 1 if zenith < 90°, else 0 |

### `hist_` — Generation history (8 features)
All history features are looked up **at issue time**, using only values observed before the forecast is issued. No leakage.

| Feature | Meaning |
|---|---|
| `hist_lag_day` | Same hour of the most recent fully observed day (lag = 24×⌈lead/24⌉) |
| `hist_lag_week_mean` | Mean of same hour over the last 7 observed days |
| `hist_last` | Most recent observed generation (at issue time) |
| `hist_mean24` | Rolling 24-h mean of generation |
| `hist_max24` | Rolling 24-h max of generation |
| `hist_resid_mean24` | Rolling 24-h mean of (observed − physics twin) residual |
| `hist_resid_mean168` | Rolling 7-day mean residual |
| `hist_absresid_mean168` | Rolling 7-day mean |residual| (trust signal) |

### `lead_h` — Lead time (1 feature)
Integer lead in hours (1–48). Used as metadata for conformal calibration bands.

---

## Model Line-up

| Name | Type | Training |
|---|---|---|
| `persistence` | Same-hour-last-day + residual bands | Seconds |
| `week_mean` | 7-day same-hour mean + residual bands | Seconds |
| `physics` | Twin on forecast weather + residual bands | None |
| `gbm` | LightGBM quantile (5 quantiles, tuned via Optuna on train holdout) | ~40 min tuning, ~15 s training per source |
| `chronos2_zs` | Amazon Chronos-2 zero-shot foundation model (comparison-only benchmark) | Kaggle 2× T4 GPUs (~1.5 min per source) |
| `ensemble` | Weighted quantile average + CQR calibration (served production model) | Seconds |

*(Per ADR-016, Chronos-2 is maintained as a comparison-only benchmark; serving in production uses `ensemble` to eliminate PyTorch runtime overhead).*

---

## Leakage Controls

- Weather features use **forecast columns** (`fx1_`, `fx2_`) matched by lead bucket (`fx0_` is never used as a lead forecast feature) — never `act_*` actual weather.
- History features use lag ≥ `24 × ⌈lead/24⌉` hours, always before the issue time.
- Train / val / test splits are **time-based by issue time**. Rows whose target timestamp crosses a split boundary are dropped.
- `assert_no_leakage()` is called on every feature column set at runtime.

---

## Feature Importance Notes (T3.2.2)

Top 5 features by LightGBM gain:
- **Solar:** `fx_ghi` (987.8k), `fx_dhi` (666.2k), `cal_cs_ghi` (518.9k), `phys_mw` (439.0k), `cal_zenith` (156.9k)
- **Wind:** `fx_ws100` (427.9k), `fx_ws100_cubed` (60.3k), `phys_mw` (21.9k), `lead_h` (21.0k), `cal_doy_cos` (15.7k)

As expected, forecast irradiation (`fx_ghi` / `fx_dhi`) and clear-sky proxy (`cal_cs_ghi`) drive the solar model, while 100m wind speed (`fx_ws100`) dominates the wind model. The physics twin (`phys_mw`) provides a highly valuable prior for both.

---

## Performance (Test Split)

Evaluated over the 179-day test split (2026-04-03 to 2026-09-28) under strict leak-free lead mapping (leads 1–24: `fx1_`, leads 25–48: `fx2_`). Six models are compared on the test split per source. Generated by the evaluation harness (`docs/accuracy-report.md`):

### Solar (40 MW AC Capacity)
- **Overall:**
  - Ensemble (served): MAE 1.57 MW (3.9% nMAE), RMSE 3.20 MW (8.0% nRMSE), bias -0.14 MW, pinball 0.380, skill vs persistence: **+27.8%**.
  - Tuned LightGBM: MAE 1.57 MW (3.9% nMAE), RMSE 3.20 MW (8.0% nRMSE), bias -0.14 MW, pinball 0.379, skill vs persistence: +27.8%.
  - Chronos-2 ZS (benchmark): MAE 1.68 MW (4.2% nMAE), RMSE 3.48 MW (8.7% nRMSE), bias +0.27 MW, pinball 0.409, skill vs persistence: +22.5%.
  - Baselines: Week-Mean MAE 1.83 MW (skill +15.5%); Physics Twin MAE 2.12 MW (skill +2.3%); Persistence MAE 2.17 MW (0.0% skill).
- **Daylight Hours Only:**
  - Ensemble: MAE 2.91 MW (7.3% nMAE), RMSE 4.36 MW (10.9% nRMSE), bias -0.26 MW, pinball 0.705, skill vs persistence: **+27.8%**.
  - Tuned LightGBM: MAE 2.91 MW (7.3% nMAE), RMSE 4.36 MW (10.9% nRMSE), bias -0.26 MW, pinball 0.703, skill vs persistence: +27.8%.
  - Chronos-2 ZS: MAE 3.12 MW (7.8% nMAE), RMSE 4.74 MW (11.9% nRMSE), bias +0.50 MW, pinball 0.759, skill vs persistence: +22.5%.
  - Persistence: MAE 4.03 MW (10.1% nMAE), RMSE 6.18 MW.
- **Uncertainty Coverage:**
  - Ensemble: PICP80 = 91.8% (daylight: 84.8%, MPIW80 25.0%), PICP90 = 96.5% (daylight: 93.6%).
  - Tuned LightGBM: PICP80 = 86.2% (daylight: 74.4%, MPIW80 21.8%), PICP90 = 91.6% (daylight: 84.5%).
  - Chronos-2 ZS: PICP80 = 89.4% (daylight: 80.3%, MPIW80 24.1%), PICP90 = 94.9% (daylight: 90.6%).
  - *Note: all-hours coverage is inflated by night-time zero-generation hours.*
- **By Lead Bucket (Ensemble):** Leads 1–24: MAE 1.51 MW (3.8% nMAE), skill +26.7%; Leads 25–48: MAE 1.62 MW (4.0% nMAE), skill +28.9%. (Tuned GBM: 1.51 MW / 1.62 MW; Chronos-2: 1.60 MW / 1.77 MW).

### Wind (50 MW Capacity)
- **Overall:**
  - Tuned LightGBM: MAE 3.99 MW (8.0% nMAE), RMSE 5.96 MW (11.9% nRMSE), bias -0.92 MW, pinball 1.011, skill vs persistence: **+38.3%**.
  - Chronos-2 ZS (benchmark): MAE 4.05 MW (8.1% nMAE), RMSE 5.94 MW (11.9% nRMSE, lowest wind RMSE overall), bias -0.09 MW, pinball 1.021, skill vs persistence: +37.4%.
  - Ensemble (served): MAE 4.15 MW (8.3% nMAE), RMSE 6.10 MW (12.2% nRMSE), bias -0.33 MW, pinball 1.059, skill vs persistence: +35.8%.
  - Baselines: Physics Twin MAE 5.26 MW (skill +18.6%); Week-Mean MAE 6.37 MW (skill +1.6%); Persistence MAE 6.47 MW (0.0% skill).
- **Uncertainty Coverage:**
  - Tuned LightGBM: PICP80 = 76.8% (MPIW80 24.6%), PICP90 = 88.1%.
  - Chronos-2 ZS: PICP80 = 74.6% (MPIW80 23.3%), PICP90 = 86.5%.
  - Ensemble: PICP80 = 72.6% (MPIW80 21.2%), PICP90 = 86.1%.
  - *Note: Wind coverage is below nominal (80% / 90%) because conformal quantile calibration was fitted on the dry winter validation window (Oct 2025 – Mar 2026), whereas the held-out test split is monsoon-heavy with higher wind speeds and variability. Tuned LightGBM improved 80% coverage by ~5.6 points (from 72.7% to 76.8%).*
- **Wind Ensemble Transfer Finding:**
  The wind ensemble got slightly worse on test (+1.5% MAE from 4.09 MW to 4.15 MW) because blend weights were fitted on the dry winter validation window and do not transfer cleanly to monsoon conditions. Both standalone tuned LightGBM (3.99 MW) and Chronos-2 (4.05 MW) outperform the ensemble on test.
- **By Lead Bucket:**
  - Leads 1–24: Chronos-2 MAE 3.74 MW (7.5% nMAE, skill +37.7%); Tuned GBM MAE 3.81 MW (7.6% nMAE, skill +36.5%); Ensemble MAE 3.92 MW (7.8% nMAE, skill +34.8%).
  - Leads 25–48: Tuned GBM MAE 4.17 MW (8.3% nMAE, skill +40.0%); Chronos-2 MAE 4.36 MW (8.7% nMAE, skill +37.1%); Ensemble MAE 4.39 MW (8.8% nMAE, skill +36.7%).

---

## Limitations

- **Virtual Plant:** While realistic and calibrated to real MP Indian data (Kaggle solar, turbine SCADA, CEA statistics), the specific hour-to-hour values do not belong to an actual operator.
- **Seasonal Distribution Shift:** Conformal calibration of wind quantiles conducted on winter validation data undercovers during the monsoon season.
- **Temporal Resolution:** Forecasts are hourly. Intra-hour ramps (15-minute) are downscaled synthetically via `models/downscale.py`.

## Attribution
Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0)
