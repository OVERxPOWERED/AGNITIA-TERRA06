# Domain glossary

| Term | Meaning |
|---|---|
| GHI / DNI / DHI | Global horizontal / direct normal / diffuse horizontal irradiance (W/m²) |
| POA | Plane-of-array irradiance on the tilted panel |
| Clear-sky index (csi) | GHI ÷ modelled clear-sky GHI; ~1 sunny, ~0.2 overcast |
| DC/AC ratio | Panel DC capacity ÷ inverter AC capacity; > 1 causes clipping at midday |
| Clipping | Inverter caps output at its AC rating |
| Capacity factor (CF) | Actual energy ÷ (capacity × hours) |
| Hub height | Height of turbine rotor centre (~80–120 m) |
| Wind shear (α) | Exponent of wind speed increase with height |
| Power curve | Turbine power vs wind speed; cut-in (~3 m/s), rated (~11–13 m/s), cut-out (~20–25 m/s) |
| Wake loss | Energy lost because downstream turbines sit in upstream turbines' wake |
| Curtailment | Plant ordered to produce less than possible (grid constraint) |
| NWP | Numerical weather prediction (ECMWF IFS, GFS, ICON…) |
| Lead time | Hours between forecast issue and target time |
| Persistence | Baseline: future = recent past (same hour yesterday) |
| Skill score | 1 − error_model / error_baseline |
| MAE / RMSE | Mean absolute / root mean squared error |
| nMAE | MAE ÷ installed capacity (%) |
| Quantile / P10, P50, P90 | Value with 10/50/90% chance of actual being below |
| Pinball loss | Proper scoring loss for quantile forecasts |
| PICP / MPIW | Prediction-interval coverage probability / mean interval width |
| CQR | Conformalized quantile regression — recalibrates bands to hit nominal coverage |
| Copula | Joins two marginal distributions with a dependence structure (solar+wind) |
| SoC / RTE | Battery state of charge / round-trip efficiency |
| DSM | Deviation Settlement Mechanism (CERC): charges for deviating from schedule |
| Time block | 15-minute scheduling interval; 96 per day |
| QCA | Qualified Coordinating Agency — submits forecasts/schedules for RE plants to SLDC |
| SLDC / RLDC / NLDC | State / Regional / National Load Despatch Centre (Grid-India runs RLDC/NLDC) |
| CERC / MPERC | Central / Madhya Pradesh Electricity Regulatory Commission |
| DISCOM | Distribution company |
| MU | Million units = GWh |
| Combined margin (CM) | Grid emission factor used for avoided-emission estimates (CEA: 0.705 tCO₂/MWh, FY2025-26) |
