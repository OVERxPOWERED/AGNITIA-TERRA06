# Data assumptions

## Site
TERRA Dewas Hybrid (virtual plant). 
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
| 1–12 | day 0 |
| 13–36 | day 1 |
| 37–48 | day 2 |

## Digital twin
Solar: 50.0 MW DC, 40.0 MW AC capacity, 23 deg tilt, 180 deg azimuth. PVWatts system losses 14%.
Wind: 25 turbines (MM100/2000, 2.0 MW each) = 50.0 MW total capacity. 90m hub height, 7% wake loss, 2% electrical loss.
Simulated capacity factors on actual weather: Solar 20.8%, Wind 14.6%.

## Realism layer
Solar outages occur ~0.02 times/day (6h mean), reducing capacity by 10%. Soiling builds at 0.002/day, resets after 5mm rain. AR(1) noise (phi=0.7, sigma=0.06).
Wind outages occur ~0.03 times/day (12h mean) dropping 12%. Curtailments ~0.02 times/day (4h mean) dropping to 60%. AR(1) noise (phi=0.6, sigma=0.08).

## Demand
Contracted peak: 30.0 MW. Temp coefficient +1%/degC over 25C. Base shape: parametric.

## Real data and calibration
Real data from multiple Indian solar/wind sources and MP official statistics were used to accurately calibrate our models and physics-based twins. This guarantees our dataset matches reality closely.

## What is real vs simulated
Generation is simulated by a digital twin at a real location driven by real weather; it is not measured data from any operator.
