# TERRA Demo Script (3-Minute Tour)

A tight, end-to-end demonstration of the TERRA hybrid forecasting platform.

---

### Step 1 (20 s) — Problem & Context
- **Pitch**: *"Co-located hybrid plants in India face tightening regulatory scrutiny. Under CERC DSM regulations (effective April 2026), tolerance bands narrow to ±5% for solar and ±10% for wind. Bad forecasts cause severe financial penalties, excessive curtailment, and reliance on carbon-heavy fossil backup."*
- **Provenance Honesty**: *"We evaluate a virtual 90 MW plant (40 MW AC solar + 50 MW wind) in Dewas, MP. Weather inputs are REAL from Open-Meteo (ECMWF IFS 0.25°, CC BY 4.0), and the digital twin is calibrated on real Indian solar, wind SCADA, and CEA data under strict leak-free lead mapping (24 h / 48 h)."*

---

### Step 2 (40 s) — Control Room Dashboard (`/`)
- **Navigation**: Open [http://localhost:3000](http://localhost:3000) (Overview page `/`).
- **Action**: Highlight the default replay run issue time: **`2026-04-10T00:00:00Z`** (05:30 IST, day-ahead morning issue).
- **Showcase**:
  - Combined hybrid generation curve alongside separate solar and wind components.
  - Solar dip coverage: Wind generation naturally peaks during early morning/evening hours when solar is zero.
  - Contracted demand profile (30 MW peak).
  - The **Trust Ribbon** indicating live model confidence across the 48-hour horizon.

---

### Step 3 (30 s) — Model Performance & Evaluation (`/models`)
- **Navigation**: Navigate to `/models`.
- **Key Metrics (Test Split, 179 Days)**:
  - **Solar (40 MW)**: Ensemble MAE 1.60 MW (4.01% nMAE), achieving **+26.1% skill over persistence**. Daylight-only MAE is 2.97 MW (7.43% nMAE).
  - **Wind (50 MW)**: Ensemble MAE 4.09 MW (8.19% nMAE), achieving **+36.7% skill over persistence**.
  - **Uncertainty Calibration**: 80% and 90% CQR bands. Solar daylight coverage reaches 85.4% (PICP80) and 93.0% (PICP90).
  - **Honesty Note**: Point out that Wind 80% coverage is 73.2% (below nominal) because conformal calibration was conducted on the dry winter validation split, while the test period is monsoon-heavy with higher wind variance.

---

### Step 4 (35 s) — Data-Driven Alerts & SSE Ingestion (`/alerts`)
- **Navigation**: Navigate to `/alerts`.
- **System Architecture**:
  - Explain how alerts reach the UI: The background `ForecastJob` in `backend/app/scheduler.py` runs on a schedule (enabled by default via `TERRA_SCHEDULER_ENABLED=true` in `backend/app/settings.py`).
  - Each tick executes `run_forecast()`, records alerts into SQLite (`terra.db` via `db.record_run()`), and broadcasts them live to the frontend via Server-Sent Events (`/alerts/stream`). In replay mode without the background scheduler running, alerts are ingested from `make forecast` and served via `/alerts`.
  - Alert thresholds are data-driven (learned from training split quantiles, ADR-010: Solar low 2.11 MW daylight, high 28.95 MW; Wind low 1.14 MW, high 18.21 MW).
- **Notable Demo Dates**:
  1. **`2026-04-10T00:00:00Z` (Default Replay)**: Shows 7 alerts, including low confidence warnings and severe demand deficit alerts (shortfall of 17–20 MW against the contracted 30 MW profile with 99% probability).
  2. **`2026-09-04T00:00:00Z` (Monsoon Cloud Cover)**: Heavy monsoon clouding drops daylight solar output to 0.45 MW, triggering `LOW_GENERATION` solar alerts below the 2.11 MW threshold.
  3. **`2026-09-26T00:00:00Z` (Monsoon Wind Surge)**: Monsoon wind gale triggers Wind `HIGH_GENERATION` alerts exceeding the 18.21 MW threshold.

---

### Step 5 (30 s) — Battery Dispatch (`/dispatch`) & Deviation Shield (`/deviation`)
- **Navigation**: Click through `/dispatch` and `/deviation`.
- **Dispatch Advisor (`/dispatch`)**:
  - Linear programming solver schedules the 25 MW / 50 MWh BESS to buffer generation deficits and avoid curtailment.
  - Across the 179-day test split, the ensemble forecast avoids **261.2 MWh of fossil backup** and **170.3 MWh of curtailment** compared to persistence (and avoids **907.3 MWh** of backup compared to a no-battery counterfactual).
  - Saves **₹25.21 Lakhs** in backup operating costs.
- **Deviation Shield (`/deviation`)**:
  - Optimizes commercial schedules against CERC DSM penalty slabs.
  - Saves **₹1,12,58,024 (~₹1.13 Crores)** in illustrative deviation penalties against persistence scheduling.

---

### Step 6 (25 s) — What-If Simulator (`/whatif`), Trust (`/trust`), Impact (`/impact`), & Assumptions (`/assumptions`)
- **Navigation**:
  - `/whatif`: Show interactive simulation (e.g. testing solar irradiance drops or battery capacity expansions).
  - `/trust`: Inspect Spearman rank correlation between trust score and actual error (-0.67 for solar, -0.50 for wind).
  - `/impact`: Review total avoided carbon emissions: **184.2 tCO2** (based on CEA CO2 Baseline Database v22.0 combined margin factor of 0.705 t/MWh).
  - `/assumptions`: Full transparency table of all site assumptions, physical constants, and data sources.
- **Closing**: *"10 modular pages, zero data leakage, verified against real Indian plant calibration and real Open-Meteo weather."*
