# India grid rules relevant to TERRA

Status markers: **[verified]** = confirmed from a source during planning; **[verify]** = must be checked against the primary document before use in numbers.

## Forecasting & scheduling
- MPERC (MP) required solar and wind generators to appoint a QCA for forecasting/scheduling — 2019 first amendment to its 2018 F&S/DSM regulations. [verified — https://mercomindia.com/madhya-pradesh-solar-wind-generators-qca]
- Schedules are in 15-minute time blocks (96/day), day-ahead with intraday revisions. [verify count/deadlines in MPERC/CERC text]

## CERC DSM Regulations 2024 — changes from 1 April 2026 [verified]
- Tolerance bands: solar & wind–solar hybrid ±10% → **±5%**; wind ±15% → **±10%**.
- Deviation basis moves from available capacity to a blend of available capacity and schedule via factor X:
  | FY | Solar/hybrid X | Wind X |
  |---|---|---|
  | 2026-27 | 100% | 100% |
  | 2027-28 | 90% | 95% |
  | 2028-29 | 75% | 85% |
  | 2029-30 | 55% | 65% |
  | 2030-31 | 30% | 35% |
  | 2031+ | 0% | 0% |
- Subject to Delhi High Court writ petitions (no coercive action against petitioners pending hearings).
- Sources: https://www.energetica-india.net/news/cerc-notifies-phased-x-factor-reduction-for-wind-and-solar-tightens-deviation-bands-from-april-2026 · https://www.mercomindia.com/cerc-notifies-phased-move-to-schedule-based-deviation-for-wind-solar-under-dsm
- **[verify]** exact deviation formula, charge slabs and rates — read the CERC notification (cercind.gov.in) in roadmap 5.7 and encode in `config/dsm.yaml`.
- Intra-state plants follow state (MPERC) regulations, which may differ. [verify]

## Emission factor [verified]
- CEA CO₂ Baseline Database v22.0 (FY2025-26): weighted average **0.675 tCO₂/MWh**, combined margin **0.705 tCO₂/MWh** (import-adjusted). Use CM for avoided emissions. https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf

## Local plants (context for pitch)
- Jamgudrani (Dewas) wind farm ≈ 62 MW, ≈ 22.96°N 76.05°E (approximate). [verified listing]
- Omkareshwar floating solar park, 600 MW planned, 22.218°N 76.185°E. [verified]
- MP hybrid tenders/projects: RUMSL 750 MW hybrid tender; Blueleaf 200 MW hybrid (Pachora ISTS). [verified]
