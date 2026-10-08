# AGNITIA-TERRA06

**TERRA** is a hybrid solar + wind generation forecasting platform for a virtual co-located plant in the Dewas wind belt near Indore. It accurately forecasts generation to avoid deviation charges, plans battery dispatch, and provides an actionable UI for grid operators.

## Screenshots
*(Add your screenshots here: Control Room, Models, Dispatch, What-if in docs/images/)*

## Hero Features
- **H1 Control Room**: Unified UI with combined bands, demand overlays, and a live trust ribbon.
- **H2 Dispatch Advisor**: Linear programming solver that minimizes fossil backup and curtailment.
- **H3 Trust Score**: Rank-correlated confidence scores to alert operators when the models are uncertain.
- **H4 What-if Simulator**: Interactive scenario planning for weather events or battery expansions.
- **H5 Deviation Shield**: Blocks optimization based on CERC DSM rules to minimize financial penalties.

## Quick Start
\\\ash
git clone https://github.com/OVERxPOWERED/AGNITIA-TERRA06.git terra-check && cd terra-check
python -m venv .venv && source .venv/Scripts/activate
make setup
make data && make calibrate && make train && make evaluate && make report && make forecast
make api            # In terminal 1
make web            # In terminal 2
\\\

## Architecture
![Architecture](docs/images/architecture.png)

## Results (Test Period)
| Source | Model | MAE | Skill vs Persistence | 80% Band Coverage |
|---|---|---|---|---|
| Solar | Ensemble | 0.66 MW | 71.4% | 91.9% |
| Wind | Ensemble | 4.16 MW | 63.6% | 85.5% |

## Data & Attribution
- Weather data provided by [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0).
- Digital twin calibrated using CEA real statistics, Kaggle Indian plant datasets, and SCADA data.

## Team
Built by OVERxPOWERED for the AGNITIA Hackathon.

## License
MIT License.
