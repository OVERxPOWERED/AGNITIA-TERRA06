# TERRA: Business Case & Impact

## 1. Problem in MP
Grid operators and renewable energy providers in Madhya Pradesh face significant challenges. As per the MPERC 2019 QCA requirement, plants must provide accurate generation forecasts. Furthermore, the CERC DSM Regulations (effective from April 1, 2026) enforce tighter tolerance bands: ±5% for solar and ±10% for wind. Deviations beyond these bands result in severe financial penalties. Bad forecasts not only lead to these penalties but also force the grid to rely on expensive, carbon-heavy backup fossil fuels.

## 2. Customers & Value
- **Plant Owners/IPPs**: Maximize revenue by avoiding deviation charges and optimizing battery dispatch.
- **QCAs (Qualified Coordinating Agencies)**: Aggregate forecasts to reduce portfolio-level penalties and improve scheduling accuracy.
- **SLDC / DISCOMs**: Gain visibility into renewable generation to better manage grid stability and reduce reliance on peaker plants.
- **C&I (Commercial & Industrial)**: Ensure reliable 24/7 green power supply by leveraging optimized battery storage alongside renewables.

## 3. Evidence
Using our TERRA digital twin and ML ensemble over a 179-day test period, we achieved:
- **Accuracy**: Ensemble model beats persistence by 71.4% (solar) and 63.6% (wind).
- **Cost Savings**: Saved ?2.53 Crores (25,382,891 INR) in operational costs and backup power.
- **DSM Penalty Reduction**: Saved ?3.18 Crores (31,857,764 INR) in deviation charges (based on illustrative rates).
- **Environmental Impact**: Avoided 2,538.7 MWh of fossil backup and prevented the emission of 1,789.8 tCO2.

## 4. Pricing Hypotheses
*These are initial hypotheses to be validated with at least three IPPs:*
- **SaaS Model**: ?5,000 per MW of installed capacity per month for full access to the Control Room and API.
- **API-Only Tier**: ?50,000 per site per month for automated scheduling integrations via the QCA.

## 5. Market Size
As of early 2025, Madhya Pradesh has a significant renewable energy footprint:
- **Madhya Pradesh**: ~5.01 GW Solar and ~2.84 GW Wind capacity (total ~10.36 GW RE).
- **India (Total)**: ~97.86 GW Solar and ~48.16 GW Wind capacity (as of Dec 2024).
This represents a massive, rapidly growing TAM (Total Addressable Market) for AI-driven forecasting and scheduling platforms.

## 6. Go-to-Market
- **Pilot**: Launch a pilot with a major plant in the Dewas or Omkareshwar region via their QCA.
- **Data Integration**: Swap our physics-based digital twin for actual plant SCADA data (our pipeline seamlessly treats the data source as configuration).
- **Expansion**: Leverage the pilot success to expand to other IPPs in MP and eventually nationwide.

## 7. Costs & Risks
- **Data Costs**: Transitioning to an Open-Meteo commercial license for production API access.
- **Regulatory Risks**: Potential changes or delays in CERC/MPERC regulations (e.g., Delhi High Court petitions on the DSM 2024 rules).
- **Integration**: Ensuring robust data pipelines and API uptime to meet strict 15-minute grid scheduling requirements.
