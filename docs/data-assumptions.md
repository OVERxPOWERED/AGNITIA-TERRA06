# Data assumptions

## Site
TERRA Dewas Hybrid (virtual plant). This is a simulated plant, not real operator data. 
Location: Jamgudrani hills wind area, Dewas district, Madhya Pradesh (Latitude: 22.96, Longitude: 76.05).
Altitude: 536.0m.

## Weather data (Open-Meteo)
APIs used:
- Previous Runs for forecast weather
- Archive for actual/historical weather
- Forecast API for live updates

Model: `ecmwf_ifs025` for forecasts.
Span: 2024-03-01 to 2026-09-30.
Licence: CC BY 4.0. The free tier is for non-commercial use.

## Timestamp convention
Timestamps use the hour-ending convention (e.g. 01:00 represents the average generation between 00:00 and 01:00). All timestamps are stored internally as UTC (`ts_utc`) and converted to IST (`Asia/Kolkata`) only for presentation. Radiation metrics (GHI/DNI) are the mean over the preceding hour, while other metrics (Temperature, Wind) are instantaneous at the timestamp.

## Lead-time mapping
The continuous 48-hour horizon is mapped into buckets:
| Lead time (hours) | Bucket |
| --- | --- |
| 1–24 | day 1 (`fx1_`, 24 h ahead) |
| 25–48 | day 2 (`fx2_`, 48 h ahead) |

## Digital twin
Solar: 50.0 MW DC, 40.0 MW AC capacity, 23 deg tilt, 180 deg azimuth. PVWatts system losses 14%, temperature coefficient gamma_pdc = -0.00434 /°C (calibrated in 2.3).
Wind: 25 turbines (MM100/2000, 2.0 MW each) = 50.0 MW total capacity. 90m hub height, 7% wake loss, 2% electrical loss.
Total hybrid plant capacity: 90.0 MW.
Simulated capacity factors on actual weather: Solar 20.8%, Wind 14.6%.

## Realism layer (calibrated from R1/R2)
Solar: Outages occur ~0.635 times/day (1.29 h mean duration), reducing capacity by 14.8%. Soiling builds at 0.002/day, resets after 5 mm rain. AR(1) noise (phi=0.8786, sigma=0.0498).
Wind: Outages occur ~0.635 times/day (1.29 h mean duration) dropping 12.0% capacity. Curtailments ~0.02 times/day (4.0 h mean) dropping to 60%. AR(1) noise (phi=0.8786, sigma=0.0498).

## Demand
Contracted peak: 30.0 MW. Temp coefficient +1%/degC over 25C. Base shape: `india_hourly` (derived from real Grid-India hourly demand series, scaled to 30 MW peak).

## Alert thresholds (data-driven, ADR-010)
Derived strictly from the training split without look-ahead:
- Low generation: P10 for solar daylight (2.11 MW) and hybrid (1.68 MW); P25 for wind (1.14 MW, justified by training calm-speed distribution).
- High generation: P90 (solar daylight: 28.95 MW, wind: 18.21 MW, hybrid: 31.70 MW).
- Ramp: P95 hourly |diff| (solar: 8.47 MW/h, wind: 8.44 MW/h, hybrid: 11.09 MW/h).

## Offline test fixtures
`data/samples/dataset_sample.parquet` is a SYNTHETIC offline test fixture used exclusively for fast offline unit tests, not real data.

## Deployment status
Deployment is currently deferred (ADR-008); cloud deployment configurations exist only as templates/config.

## What is real vs simulated

| Item | Real or simulated | Source / method |
|---|---|---|
| Weather inputs (actual and forecast) | Real | Open-Meteo Archive + Previous Runs, model `ecmwf_ifs025`, CC BY 4.0 |
| Solar & wind generation at the Dewas site | Simulated (digital twin) | pvlib + windpowerlib + realism layer (virtual plant, not operator data) |
| Twin temperature coefficient, noise, outages | Calibrated on real data | R1 (Kaggle Indian plants), R2 (turbine SCADA) |
| Twin seasonal capacity factor | Checked against real statistics | R4 CEA monthly MP |
| Demand shape | Real shape, scaled | R3 all-India hourly demand |
| Real-generation benchmark | Real | R1 (plant), R3 (all-India) |
| Deviation charge rates | Illustrative until verified | config/dsm.yaml (`verify: true`) |

