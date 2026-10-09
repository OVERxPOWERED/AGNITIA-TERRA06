# TERRA Demo Script (3-Minute Tour)

A tight, end-to-end demonstration of the TERRA hybrid forecasting platform.

---

### Step 1 (20 s) — Problem & Context
- **Pitch**: *"Co-located hybrid plants in India face tightening regulatory scrutiny. Under CERC DSM regulations (effective April 2026), tolerance bands narrow to ±5% for solar and ±10% for wind. Bad forecasts cause severe financial penalties, excessive curtailment, and reliance on carbon-heavy fossil backup."*
- **Provenance Honesty**: *"We evaluate a virtual 90 MW plant (40 MW AC solar + 50 MW wind) in Dewas, MP. Weather inputs are REAL from Open-Meteo (ECMWF IFS 0.25°, CC BY 4.0), and the digital twin is calibrated on real Indian solar, wind SCADA, and CEA data under strict leak-free lead mapping (24 h / 48 h)."*

---

### Step 2 (40 s) — Control Room Dashboard (`/`) & Forecast Explorer (`/forecast`)
- **Navigation**: Open [http://localhost:3000](http://localhost:3000) (Overview page `/`).
- **Action**: Highlight the default replay run issue time from `artifacts/runs/LATEST/run.json`: **`2026-04-10T00:00:00Z`** (05:30 IST, day-ahead morning replay issue, with 7 alerts).
- **Showcase**:
  - Combined hybrid generation curve alongside separate solar and wind components.
  - Solar dip coverage: Wind generation naturally peaks during early morning/evening hours when solar is zero.
  - Contracted demand profile (30 MW peak).
  - The **Trust Ribbon** indicating live model confidence across the 48-hour horizon.
  - Navigate to **Forecast Explorer (`/forecast`)**: Demonstrate the model segmented selector (`Ensemble`, `LightGBM`, `Physics`, `Persistence`, and `Chronos-2 (Zero-shot)` benchmark) allowing operators to inspect individual model forecasts against actual generation and calibrated intervals.

---

### Step 3 (30 s) — Model Performance & Evaluation (`/models`)
- **Navigation**: Navigate to `/models`.
- **Key Metrics (Test Split, 179 Days)**:
  - Six models evaluated on the test split per source, with `chronos2_zs` tagged with the "benchmark" badge.
  - **Solar (40 MW)**: Ensemble MAE 1.57 MW (3.9% nMAE), achieving **+27.8% skill over persistence** (RMSE 3.20 MW). Standalone tuned LightGBM achieves identical 1.57 MW MAE (+27.8% skill). External benchmark Chronos-2 zero-shot achieves 1.68 MW MAE (4.2% nMAE, +22.5% skill). Daylight-only MAE is 2.91 MW (7.3% nMAE, +27.8% skill).
  - **Wind (50 MW)**: Standalone tuned LightGBM achieves MAE 3.99 MW (8.0% nMAE, **+38.3% skill**). Chronos-2 zero-shot benchmark achieves MAE 4.05 MW (8.1% nMAE, +37.4% skill) with the **lowest wind RMSE overall (5.94 MW)**. Ensemble MAE is 4.15 MW (8.3% nMAE, +35.8% skill).
  - **Uncertainty Calibration**: 80% and 90% CQR bands. Solar daylight coverage reaches 84.8% (PICP80) and 93.6% (PICP90).
  - **Honesty Notes**:
    1. Point out that Wind 80% coverage is 72.6% for ensemble and 76.8% for tuned LightGBM (below nominal) because conformal calibration was conducted on the dry winter validation split, while the test period is monsoon-heavy with higher wind variance.
    2. Disclose the wind ensemble transfer finding: blend weights fitted on winter validation do not transfer cleanly to monsoon conditions, so standalone tuned LightGBM (3.99 MW) and Chronos-2 (4.05 MW) outperform the ensemble (4.15 MW) on test.
    3. Chronos-2 is a comparison-only benchmark; it is omitted from serving to avoid PyTorch deployment overhead.

---

### Step 4 (35 s) — Data-Driven Alerts & Ingestion (`/alerts`)
- **Navigation**: Navigate to `/alerts`.
- **System Architecture**:
  - Explain how alerts reach the UI: The background `ForecastJob` in `backend/app/scheduler.py` runs on a schedule (enabled via `TERRA_SCHEDULER_ENABLED=true` in `backend/app/settings.py`).
  - Each tick executes `run_forecast()`, records alerts into SQLite (`terra.db` via `db.record_run()`), and broadcasts them live to the frontend via Server-Sent Events (`/alerts/stream`). In replay mode without the background scheduler running, alerts are ingested from `make forecast` (or `artifacts/runs/LATEST`) and served via `/alerts`.
  - Alert thresholds are data-driven (learned from training split quantiles, ADR-010: Solar low 2.11 MW daylight, high 28.95 MW; Wind low 1.14 MW, high 18.21 MW; Hybrid low 1.68 MW, high 31.70 MW).
- **Notable Demo Dates (Replay Mode)**:
  1. **`2026-04-10T00:00:00Z` (Default Replay)**: Shows 7 alerts, including low confidence warnings and severe demand deficit alerts (shortfall of 17–20 MW against the contracted 30 MW profile with 99% probability).
  2. **`2026-09-04T00:00:00Z` (Monsoon Cloud Cover)**: Heavy monsoon clouding drops daylight solar output to 0.45 MW, triggering `LOW_GENERATION` solar alerts below the 2.11 MW threshold.
  3. **`2026-09-26T00:00:00Z` (Monsoon Wind Surge)**: Monsoon wind gale triggers Wind `HIGH_GENERATION` alerts exceeding the 18.21 MW threshold.

---

### Step 5 (30 s) — Battery Dispatch (`/dispatch`) & Deviation Shield (`/deviation`)
- **Navigation**: Click through `/dispatch` and `/deviation`.
- **Dispatch Advisor (`/dispatch`)**:
  - Linear programming solver schedules the 25 MW / 50 MWh BESS to buffer generation deficits and avoid curtailment.
  - Across the 179-day test split, the ensemble forecast avoids **304.7 MWh of fossil backup** and **248.9 MWh of curtailment** compared to persistence (and avoids **950.7 MWh** of backup compared to a no-battery counterfactual).
  - Saves **₹29,90,857 (~₹29.91 Lakhs)** in backup operating costs.
- **Deviation Shield (`/deviation`)**:
  - Optimizes commercial schedules against CERC DSM penalty slabs.
  - Saves **₹1,11,45,303 (~₹1.11 Crores / ₹111.45 Lakhs)** in illustrative deviation penalties against persistence scheduling (Solar penalties reduced from ₹53.66 Lakhs to ₹26.65 Lakhs; Wind penalties reduced from ₹1.28 Crores to ₹43.53 Lakhs).

---

### Step 6 (25 s) — What-If Simulator (`/whatif`), Trust (`/trust`), Impact (`/impact`), & Assumptions (`/assumptions`)
- **Navigation**:
  - `/whatif`: Show interactive simulation (e.g. testing solar irradiance drops or battery capacity expansions).
  - `/trust`: Inspect Spearman rank correlation between trust score and actual error (**-0.665 for solar**, **-0.518 for wind**; MAE drops monotonically from low trust to high trust).
  - `/impact`: Review total avoided carbon emissions: **214.8 tCO2** (based on CEA CO2 Baseline Database v22.0 combined margin factor of 0.705 t/MWh).
  - `/assumptions`: Full transparency table of all site assumptions, physical constants, and data sources.
- **Closing**: *"10 modular pages, zero data leakage, verified against real Indian plant calibration and real Open-Meteo weather."*
