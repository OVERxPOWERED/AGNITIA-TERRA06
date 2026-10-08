# Model Card — TERRA Forecasting Models

**Plant**: Virtual co-located solar + wind plant, Dewas wind belt, Madhya Pradesh, India  
**Capacity**: 50 MW solar (AC) + 50 MW wind = 100 MW total  
**Data**: Digital twin generated from real Open-Meteo weather, calibrated on real Indian plant data (Phase 2)  
**Horizon**: 1–48 h ahead, issued at 00:00 / 12:00 UTC  
**Targets**: `solar_mw` (AC generation), `wind_mw` (net-of-wake output)  

> [!IMPORTANT]
> Generation is **simulated** by a calibrated digital twin at a real location. All metrics are on held-out test data (time-based split, no shuffle). No actual operator data.

---

## Feature Set (34 features, same for solar and wind)

### `fx_` — Forecast weather (16 features)
Feature-lead matching: leads 1–12 → `fx0_`, leads 13–36 → `fx1_`, leads 37–48 → `fx2_` (day-ahead previous-run)

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
| `gbm` | LightGBM quantile (5 quantiles, one booster each) | ~1 min per source |
| `chronos2_zs` | Chronos-2 zero-shot | Inference only |
| `chronos2_ft` | Chronos-2 LoRA fine-tuned | ≤ 2 h on Kaggle GPU |
| `ensemble` | Weighted quantile average + CQR calibration | Seconds |

---

## Leakage Controls

- Weather features use **forecast columns** (`fx0_`, `fx1_`, `fx2_`) matched by lead bucket — never `act_*` actual weather.
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

The final ensemble achieves excellent test metrics (MAE and skill vs persistence):
- **Solar:** MAE 0.66 MW (1.6% nMAE), +71.4% skill vs persistence.
- **Wind:** MAE 4.16 MW (8.3% nMAE), +63.6% skill vs persistence.

(Chronos-2 skipped as no GPU was available locally).

---

## Limitations

- **Virtual Plant:** While realistic and calibrated to real MP Indian data, the specific hour-to-hour values do not belong to an actual operator.
- **Temporal Resolution:** Forecasts are hourly. Intra-hour ramps (15-minute) are downscaled synthetically via `models/downscale.py`.

## Attribution
Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0)
