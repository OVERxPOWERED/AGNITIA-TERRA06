# Data contracts

All internal tables: Parquet, index `ts_utc` (tz-aware UTC, hourly, hour-beginning after convention shift — confirm in roadmap 1.1).

## Weather variables (base names)
| Name | Unit | Open-Meteo variable |
|---|---|---|
| `ghi` | W/m² | shortwave_radiation |
| `dni` | W/m² | direct_normal_irradiance |
| `dhi` | W/m² | diffuse_radiation |
| `cloud` | % | cloud_cover |
| `t2m` | °C | temperature_2m |
| `rh2m` | % | relative_humidity_2m |
| `psfc` | hPa | surface_pressure |
| `ws10` | m/s | wind_speed_10m (request `wind_speed_unit=ms`) |
| `ws100` | m/s | wind_speed_100m |
| `wd100` | ° | wind_direction_100m |
| `gust10` | m/s | wind_gusts_10m (if available) |
| `precip` | mm | precipitation |
Derived: `rho` (kg/m³ air density), `wd100_sin`, `wd100_cos`, `csi` (clear-sky index), `shear_alpha`.

## Prefixes
| Prefix | Meaning | Allowed as feature? |
|---|---|---|
| `act_` | actual weather (Archive/reanalysis) | **No** — drives the twin only |
| `fx0_` | forecast, `_previous_day0` | Yes (lead 1–12 h) |
| `fx1_` | forecast, `_previous_day1` (24 h ahead) | Yes (lead 13–36 h) |
| `fx2_` | forecast, `_previous_day2` (48 h ahead) | Yes (lead 37–48 h) |
| `fx_` | lead-resolved forecast after framing | Yes |
| `phys_` | physics model output on forecast weather | Yes |
| `hist_` | generation history ≤ issue time | Yes |
| `cal_` | calendar / solar geometry | Yes |

## `data/processed/dataset.parquet`
| Column | Unit | Notes |
|---|---|---|
| `act_*`, `fx0_*`, `fx1_*`, `fx2_*` | see above | weather |
| `solar_mw` | MW (AC) | target, twin + realism |
| `wind_mw` | MW | target, twin + realism |
| `demand_mw` | MW | scaled real Indian demand shape |
| `solar_outage`, `wind_outage`, `wind_curtailed` | bool | realism flags |
| `gap_flag` | bool | weather gap > 3 h |

## Framed training table (`data/processed/framed_<source>.parquet`)
Columns: `issue_time_utc`, `target_time_utc`, `lead_h` (1–48), `lead_bucket` (`1-12|13-36|37-48`), features (`fx_*`, `phys_*`, `hist_*`, `cal_*`), `y` (MW), `split` (`train|val|test`).

## Forecast output (long format, `predictions.parquet` and API)
| Column | Type |
|---|---|
| `issue_time_utc` | timestamp |
| `target_time_utc` | timestamp |
| `lead_h` | int |
| `source` | `solar` \| `wind` \| `hybrid` |
| `model` | `persistence` \| `smart_persistence` \| `physics` \| `gbm` \| `chronos2_zs` \| `chronos2_ft` \| `ensemble` |
| `q05,q10,q50,q90,q95` | float MW |
| `actual_mw` | float MW (nullable, backtests only) |
| `trust_score` | 0–100 (ensemble only) |

## Alert object
`id, type (LOW_GENERATION|HIGH_GENERATION|RAMP|LOW_CONFIDENCE|DEFICIT_VS_DEMAND), source, start_utc, end_utc, severity (info|warning|critical), probability, magnitude_mw, message, issue_time_utc`.

## Real datasets (Phase 2) — stored under `data/external/<name>/`, cleaned to `data/interim/real/<name>.parquet`
| ID | Name | Key columns after cleaning |
|---|---|---|
| R1 | kaggle_solar_india | `plant_id, ac_mw, dc_mw, irradiation_wm2, t_amb, t_mod, inverter_outage` |
| R2 | wind_scada | `power_kw, ws_ms, wd_deg, theoretical_kw, downtime, curtailed` |
| R3 | india_hourly | `demand_mw, solar_mw, wind_mw` (all-India) |
| R4 | cea_mp_monthly | `month, source, generation_mu, capacity_mw, cf` |
| R5 | edp_scada (optional) | as R2 |
