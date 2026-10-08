# TERRA: Business Case & Impact

## 1. Problem in MP
Grid operators and renewable energy providers in Madhya Pradesh face significant challenges. As per the MPERC 2019 QCA requirement, plants must provide accurate generation forecasts. Furthermore, the CERC DSM Regulations (effective from April 1, 2026; illustrative framework, verify before external use) enforce tighter tolerance bands: ±5% for solar and ±10% for wind. Deviations beyond these bands result in severe financial penalties. Bad forecasts not only lead to these penalties but also force the grid to rely on expensive, carbon-heavy backup fossil fuels.

## 2. Customers & Value
- **Plant Owners/IPPs**: Maximize revenue by avoiding deviation charges and optimizing battery dispatch.
- **QCAs (Qualified Coordinating Agencies)**: Aggregate forecasts to reduce portfolio-level penalties and improve scheduling accuracy.
- **SLDC / DISCOMs**: Gain visibility into renewable generation to better manage grid stability and reduce reliance on peaker plants.
- **C&I (Commercial & Industrial)**: Ensure reliable 24/7 green power supply by leveraging optimized battery storage alongside renewables.

## 3. Evidence
Using our TERRA calibrated digital twin (40 MW AC solar + 50 MW wind = 90 MW total at Dewas, MP) evaluated on real Open-Meteo weather over the held-out 179-day test period under strict leak-free lead mapping, we achieved:
- **Accuracy**: Ensemble model achieves skill over persistence of 26.1% (solar: MAE 1.60 MW vs 2.17 MW) and 36.7% (wind: MAE 4.09 MW vs 6.47 MW).
- **Cost Savings**: Saved ₹25,21,213 (~₹25.21 Lakhs) in operational and fossil backup costs over 179 days compared to persistence dispatch (₹43,70,13,160 vs ₹43,95,34,373).
- **DSM Penalty Reduction**: Saved ₹1,12,58,024 (~₹1.13 Crores) in deviation charges over 179 days compared to persistence scheduling (illustrative rates; verify before external use). Solar penalties fell from ₹53.66 Lakhs to ₹27.16 Lakhs; wind penalties fell from ₹1.28 Crores to ₹41.47 Lakhs.
- **Environmental Impact**: Avoided 261.2 MWh of fossil backup and 170.3 MWh of curtailment vs persistence (907.3 MWh backup avoided vs a no-battery counterfactual), preventing 184.2 tCO2 of emissions (CEA CO2 Baseline Database v22.0 combined margin factor: 0.705 tCO2/MWh, FY2025-26).

## 4. Pricing Hypotheses
*These are initial hypotheses to be validated with at least three IPPs (illustrative; verify before external use):*
- **SaaS Model**: ₹5,000 per MW of installed capacity per month for full access to the Control Room and API.
- **API-Only Tier**: ₹50,000 per site per month for automated scheduling integrations via the QCA.

## 5. Market Size (illustrative; verify before external use)
As of early 2025, Madhya Pradesh and India have a significant renewable energy footprint (illustrative; verify before external use):
- **Madhya Pradesh**: ~5.01 GW Solar and ~2.84 GW Wind capacity (total ~10.36 GW RE) [illustrative; verify before external use].
- **India (Total)**: ~97.86 GW Solar and ~48.16 GW Wind capacity (as of Dec 2024) [illustrative; verify before external use].
This represents a massive, rapidly growing TAM (Total Addressable Market) for AI-driven forecasting and scheduling platforms.

## 6. Go-to-Market
- **Pilot**: Launch a pilot with a major plant in the Dewas or Omkareshwar region via their QCA.
- **Data Integration**: Swap our physics-based digital twin for actual plant SCADA data (our pipeline seamlessly treats the data source as configuration).
- **Expansion**: Leverage the pilot success to expand to other IPPs in MP and eventually nationwide.

## 7. Costs & Risks
- **Data Costs**: Transitioning to an Open-Meteo commercial license for production API access.
- **Regulatory Risks**: Potential changes or delays in CERC/MPERC regulations (e.g., Delhi High Court petitions on the DSM 2024 rules).
- **Integration**: Ensuring robust data pipelines and API uptime to meet strict 15-minute grid scheduling requirements.
