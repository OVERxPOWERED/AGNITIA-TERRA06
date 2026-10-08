# IMPLEMENTATION COMPLETION — AGNITIA TERRA06 (v3 tracker)

Task-level tracker for [`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md). Every task ID (`T<phase>.<sub>.<n>`) matches a `####` heading in the roadmap. This replaces `COMPLETION.md` (v2) for build tracking.

## How to update (humans and AI agents)

1. Before starting a task: change `[ ]` → `[~]`.
2. When the task's **Check** passes: change `[~]` → `[x]` and append the date, e.g. `- [x] T1.4.1 … ✅ 2026-10-10`.
3. Skipped on purpose: `[-]` plus a reason in the log (e.g. "4.4 skipped: fine-tune exceeded 2 h time box").
4. When **all tasks of a subphase** are `[x]`/`[-]`, update the progress table below and add one line to the log (newest first).
5. Never tick a task whose Check you did not actually run.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` skipped · ✅ copy tested code · 🧩 spec code · 📝 write/do from instructions · **[verify]** confirm a fact first

**Last updated:** 2026-10-08 — tracker created; build not started.

## Progress

| Phase | Name | Subphases done | Tasks done | Target days |
|---|---|---|---|---|
| 0 | Foundations | 7 / 7 | 23 / 23 | Day 1 |
| 1 | Weather data & digital twin | 9 / 9 | 18 / 18 | Day 1–2 |
| 2 | Real plant data & calibration | 8 / 8 | 30 / 30 | Day 2–3 |
| 3 | Features, baselines, evaluation harness | 5 / 5 | 13 / 13 | Day 3 |
| 4 | ML models | 0 / 9 | 0 / 19 | Day 4–5 |
| 5 | Engines: hero features, revenue & impact | 0 / 9 | 0 / 12 | Day 5–7 |
| 6 | Backend API | 0 / 6 | 0 / 17 | Day 5–7, in parallel with Phase 5 |
| 7 | Frontend | 0 / 13 | 0 / 22 | Day 4–9 |
| 8 | Integration | 0 / 5 | 0 / 13 | Day 8–9 |
| 9 | Docs, business case, report, demo | 0 / 8 | 0 / 10 | Day 9–10 |
| | **Total** | **29 / 79** | **84 / 177** | |

---

## Phase 0 — Foundations (Day 1)

### 0.1 Repo scaffold & conventions
- [x] T0.1.1 Root config files — ✅ Tested ✅ 2026-10-08
- [x] T0.1.2 LICENSE — 📝 Write from spec ✅ 2026-10-08
- [x] T0.1.3 README skeleton — 📝 Write from spec ✅ 2026-10-08
- [x] T0.1.4 Data and artifact folders — 📝 Write from spec ✅ 2026-10-08
- [x] T0.1.5 First commit — 📝 ✅ 2026-10-08

### 0.2 Python environment for `ml/`
- [x] T0.2.1 `ml/pyproject.toml` — ✅ Tested ✅ 2026-10-08
- [x] T0.2.2 Package skeleton — 📝 Write from spec ✅ 2026-10-08
- [x] T0.2.3 Create the virtual environment and install — 📝 ✅ 2026-10-08
- [x] T0.2.4 Align the agent rule files with this guide — 📝 ✅ 2026-10-08

### 0.3 Site & plant configuration
- [x] T0.3.1 `config/site.yaml` — ✅ Tested ✅ 2026-10-08
- [x] T0.3.2 `config/dsm.yaml` — ✅ Tested ✅ 2026-10-08
- [x] T0.3.3 `paths.py` and `logs.py` — ✅ Tested ✅ 2026-10-08
- [x] T0.3.4 `schema.py` (column-name contract) — ✅ Tested ✅ 2026-10-08
- [x] T0.3.5 `config.py` (typed config) — ✅ Tested ✅ 2026-10-08
- [x] T0.3.6 Test fixtures and config tests — ✅ Tested ✅ 2026-10-08
- [x] T0.3.7 Confirm site facts — 📝 [verify] ✅ 2026-10-08

### 0.4 Frontend scaffold
- [x] T0.4.1 Create the Next.js app — 📝 ✅ 2026-10-08
- [x] T0.4.2 Remove template content — 📝 ✅ 2026-10-08

### 0.5 Backend scaffold
- [x] T0.5.1 `backend/pyproject.toml` and `.env.example` — ✅ Tested ✅ 2026-10-08
- [x] T0.5.2 Package skeleton and temporary app — 📝 ✅ 2026-10-08

### 0.6 CI & dev ergonomics
- [x] T0.6.1 Makefile — ✅ Tested ✅ 2026-10-08
- [x] T0.6.2 GitHub Actions CI — ✅ Tested, 📝 ✅ 2026-10-08

### 0.7 AI agent tooling
- [x] T0.7.1 Verify agent files — 📝 ✅ 2026-10-08

## Phase 1 — Weather data & digital twin (Day 1–2)

### 1.1 API reconnaissance & freeze
- [x] T1.1.1 Recon notebook — 📝 [verify] ✅ 2026-10-08
- [x] T1.1.2 Data-assumptions draft — 📝 ✅ 2026-10-08

### 1.2 Weather ingestion client with caching
- [x] T1.2.1 `openmeteo.py` — ✅ Tested, 🧩 ✅ 2026-10-08
- [x] T1.2.2 Client tests — ✅ Tested ✅ 2026-10-08

### 1.3 Weather tables (actual vs forecast) and alignment
- [x] T1.3.1 Synthetic weather generator (offline development and tests) — ✅ Tested ✅ 2026-10-08
- [x] T1.3.2 `weather_tables.py` — ✅ Tested ✅ 2026-10-08
- [x] T1.3.3 Fetch the real weather — 📝 ✅ 2026-10-08

### 1.4 Solar digital twin (pvlib)
- [x] T1.4.1 `solar_twin.py` — ✅ Tested ✅ 2026-10-08

### 1.5 Wind digital twin
- [x] T1.5.1 `wind_twin.py` — ✅ Tested ✅ 2026-10-08

### 1.6 Realism layer
- [x] T1.6.1 `realism.py` — ✅ Tested ✅ 2026-10-08

### 1.7 Demand profile
- [x] T1.7.1 `demand.py` — ✅ Tested · 🧩 ✅ 2026-10-08

### 1.8 Dataset assembly, quality checks, data card
- [x] T1.8.1 `build_dataset.py` — ✅ Tested ✅ 2026-10-08
- [x] T1.8.2 `quality.py` — ✅ Tested ✅ 2026-10-08
- [x] T1.8.3 Twin and dataset tests — ✅ Tested ✅ 2026-10-08
- [x] T1.8.4 Complete the data card (twin part) — 📝 ✅ 2026-10-08

### 1.9 CLI & offline bootstrap
- [x] T1.9.1 `pipelines/cli.py` (all commands, used by every later phase) — ✅ Tested ✅ 2026-10-08
- [x] T1.9.2 Build the real dataset — 📝 ✅ 2026-10-08
- [x] T1.9.3 Synthetic end-to-end bootstrap — 📝 ✅ 2026-10-08

## Phase 2 — Real plant data & calibration (Day 2–3)

### 2.1 Acquire real datasets
- [x] T2.1.1 Kaggle API token — 📝 ✅ 2026-10-08
- [x] T2.1.2 R1 Indian solar plants — 📝 [verify] ✅ 2026-10-08
- [x] T2.1.3 R2 wind turbine SCADA — 📝 [verify] ✅ 2026-10-08
- [x] T2.1.4 R3 all-India hourly generation — 📝 [verify] ✅ 2026-10-08
- [x] T2.1.5 R4 Madhya Pradesh monthly statistics — 📝 [verify] ✅ 2026-10-08
- [x] T2.1.6 `real/loaders.py` — 🧩 Spec code ✅ 2026-10-08

### 2.2 Profile & clean real data
- [x] T2.2.1 Resolve every [verify] in the loaders — 📝 ✅ 2026-10-08
- [x] T2.2.2 Save cleaned copies — 📝 ✅ 2026-10-08
- [x] T2.2.3 Switch demand to the real Indian shape — 📝 ✅ 2026-10-08
- [x] T2.2.4 Profiling notebook — 📝 ✅ 2026-10-08

### 2.3 Calibrate the solar twin on real Indian plants (R1)
- [x] T2.3.1 `real/calibrate_solar.py` — 🧩 Spec code ✅ 2026-10-08
- [x] T2.3.2 Run it — 📝 ✅ 2026-10-08
- [x] T2.3.3 Apply the calibrated values — 📝 ✅ 2026-10-08
- [x] T2.3.4 Document — 📝 ✅ 2026-10-08

### 2.4 Calibrate the wind twin on real SCADA (R2)
- [x] T2.4.1 `real/calibrate_wind.py` — 🧩 Spec code ✅ 2026-10-08
- [x] T2.4.2 Run it — 📝 ✅ 2026-10-08
- [x] T2.4.3 Apply — 📝 ✅ 2026-10-08
- [x] T2.4.4 Document — 📝 ✅ 2026-10-08

### 2.5 Calibrate to Madhya Pradesh monthly statistics (R4)
- [x] T2.5.1 `real/calibrate_state.py` — 🧩 Spec code ✅ 2026-10-08
- [x] T2.5.2 Run it — 📝 ✅ 2026-10-08
- [x] T2.5.3 Apply monthly scaling only if needed — 🧩 SNIPPET ✅ 2026-10-08
- [x] T2.5.4 Document — 📝 ✅ 2026-10-08

### 2.6 Real-data benchmark A — Indian solar plants
- [x] T2.6.1 `real/benchmarks.py` — 🧩 Spec code ✅ 2026-10-08
- [x] T2.6.2 Run benchmark A — 📝 ✅ 2026-10-08
- [x] T2.6.3 Interpret — 📝 ✅ 2026-10-08

### 2.7 Real-data benchmark B — all-India hourly solar & wind
- [x] T2.7.1 Choose the hub list — 📝 [verify] ✅ 2026-10-08
- [x] T2.7.2 Run benchmark B — 📝 ✅ 2026-10-08
- [x] T2.7.3 Sanity checks — 📝 ✅ 2026-10-08
- [x] T2.7.4 Document — 📝 ✅ 2026-10-08

### 2.8 Real-vs-simulated provenance card
- [x] T2.8.1 Provenance table — 📝 ✅ 2026-10-08

## Phase 3 — Features, baselines, evaluation harness (Day 3)

### 3.1 Forecast framing & splits
- [x] T3.1.1 `features/framing.py` — ✅ Tested ✅ 2026-10-08
- [x] T3.1.2 `features/build_features.py` — ✅ Tested ✅ 2026-10-08
- [x] T3.1.3 Leakage tests — ✅ Tested ✅ 2026-10-08
- [x] T3.1.4 Frame the real dataset — 📝 ✅ 2026-10-08

### 3.2 Feature review
- [x] T3.2.1 Feature list in the model card — 📝 ✅ 2026-10-08
- [x] T3.2.2 Importance sanity check — 📝 ✅ 2026-10-08

### 3.3 Baseline models
- [x] T3.3.1 `models/base.py` (interface, quantile helpers, residual bands) — ✅ Tested ✅ 2026-10-08
- [x] T3.3.2 `models/baselines.py` (M0) — ✅ Tested ✅ 2026-10-08
- [x] T3.3.3 `models/physics.py` (M1) — ✅ Tested ✅ 2026-10-08

### 3.4 Metrics & backtest harness
- [x] T3.4.1 `eval/metrics.py` — ✅ Tested ✅ 2026-10-08
- [x] T3.4.2 `eval/backtest.py` — ✅ Tested ✅ 2026-10-08
- [x] T3.4.3 Metric tests — ✅ Tested ✅ 2026-10-08

### 3.5 Baseline report
- [x] T3.5.1 Baseline results on validation — ✅ Tested ✅ 2026-10-08

## Phase 4 — ML models (Day 4–5)

### 4.1 LightGBM point + quantile model
- [ ] T4.1.1 `models/gbm.py` — ✅ Tested
- [ ] T4.1.2 Model tests — ✅ Tested

### 4.2 Quantile models
- [ ] T4.2.1 Confirm quantile behaviour — 📝

### 4.3 Chronos-2 zero-shot with covariates
- [ ] T4.3.1 `models/chronos2.py` — 🧩 Spec code
- [ ] T4.3.2 Build and upload the Kaggle bundle — 📝
- [ ] T4.3.3 Kaggle inference notebook — 🧩 Spec code
- [ ] T4.3.4 Bring results back — 📝

### 4.4 Chronos-2 LoRA fine-tune on Kaggle
- [ ] T4.4.1 Fine-tune notebook — 🧩 Spec code
- [ ] T4.4.2 Save the checkpoint and outputs — 📝
- [ ] T4.4.3 If fine-tuning is skipped — 📝

### 4.5 Time-boxed GBM tuning
- [ ] T4.5.1 Tuning script — ✅ Tested

### 4.6 Ensemble
- [ ] T4.6.1 `models/ensemble.py` — ✅ Tested

### 4.7 Conformal calibration (CQR)
- [ ] T4.7.1 `models/conformal.py` — ✅ Tested

### 4.8 Registry, bundle, training pipeline, model card
- [ ] T4.8.1 `models/registry.py` — ✅ Tested
- [ ] T4.8.2 `pipelines/bundle.py` — ✅ Tested
- [ ] T4.8.3 `pipelines/train.py` — ✅ Tested
- [ ] T4.8.4 Train for real — 📝
- [ ] T4.8.5 Model card — 📝

### 4.9 15-minute block downscaler
- [ ] T4.9.1 `models/downscale.py` — ✅ Tested

## Phase 5 — Engines: hero features, revenue & impact (Day 5–7)

### 5.1 H1 — Hybrid engine
- [ ] T5.1.1 `engines/hybrid.py` — ✅ Tested

### 5.2 H3 — Trust engine
- [ ] T5.2.1 `engines/trust.py` — ✅ Tested

### 5.3 Alerts engine
- [ ] T5.3.1 `engines/alerts.py` — ✅ Tested

### 5.4 H2 — Battery Dispatch Advisor
- [ ] T5.4.1 `engines/dispatch.py` — ✅ Tested

### 5.5 Value-of-forecast backtest
- [ ] T5.5.1 `engines/value_of_forecast.py` — ✅ Tested

### 5.6 H4 — What-if engine
- [ ] T5.6.1 `engines/whatif.py` — ✅ Tested

### 5.7 H5 — Deviation Shield (DSM)
- [ ] T5.7.1 `engines/dsm.py` — ✅ Tested
- [ ] T5.7.2 Verify the regulation and replace illustrative rates — 📝 [verify]

### 5.8 Impact engine
- [ ] T5.8.1 `engines/impact.py` — ✅ Tested

### 5.9 Engine tests, evaluation pipeline, accuracy report
- [ ] T5.9.1 Engine tests — ✅ Tested
- [ ] T5.9.2 `pipelines/evaluate.py` — ✅ Tested
- [ ] T5.9.3 `eval/report.py` (accuracy report generator) — ✅ Tested

## Phase 6 — Backend API (Day 5–7, in parallel with Phase 5)

### 6.1 API contract
- [ ] T6.1.1 `app/schemas/api.py` — ✅ Tested
- [ ] T6.1.2 Update the contract document — 📝

### 6.2 Forecast pipeline & scheduler
- [ ] T6.2.1 `ml/terra/pipelines/forecast.py` — ✅ Tested · 🧩
- [ ] T6.2.2 Replay run — 📝
- [ ] T6.2.3 Live run — 📝
- [ ] T6.2.4 `app/scheduler.py` — ✅ Tested

### 6.3 Settings & storage
- [ ] T6.3.1 `app/settings.py` — ✅ Tested
- [ ] T6.3.2 `app/db/models.py` — ✅ Tested

### 6.4 Services, routes, app
- [ ] T6.4.1 `app/services/runs.py` — ✅ Tested
- [ ] T6.4.2 `app/services/whatif.py` — ✅ Tested
- [ ] T6.4.3 Route modules — ✅ Tested
- [ ] T6.4.4 `app/main.py` (replaces the temporary file from T0.5.2) — ✅ Tested

### 6.5 Replay mode & live updates
- [ ] T6.5.1 Configure and observe replay — 📝
- [ ] T6.5.2 Live mode — 📝

### 6.6 Backend tests & CI
- [ ] T6.6.1 `backend/tests/test_api.py` — ✅ Tested
- [ ] T6.6.2 Run the tests — 📝
- [ ] T6.6.3 Re-enable the full CI job — 📝

## Phase 7 — Frontend (Day 4–9)

### 7.1 Design system & layout
- [ ] T7.1.1 Theme tokens — ✅ Tested
- [ ] T7.1.2 Utilities — ✅ Tested
- [ ] T7.1.3 UI primitives and query states — ✅ Tested
- [ ] T7.1.4 App shell, providers, layout — ✅ Tested

### 7.2 API client & state
- [ ] T7.2.1 Generate API types — 📝
- [ ] T7.2.2 Fetch wrapper and type aliases — ✅ Tested
- [ ] T7.2.3 Data hooks (one per endpoint) + SSE — ✅ Tested

### 7.3 Control Room (H1)
- [ ] T7.3.1 Chart building blocks — ✅ Tested
- [ ] T7.3.2 Control Room page — ✅ Tested

### 7.4 Forecast Explorer (actual vs predicted)
- [ ] T7.4.1 `forecast/page.tsx` — ✅ Tested

### 7.5 Models & Accuracy
- [ ] T7.5.1 `models/page.tsx` — ✅ Tested
- [ ] T7.5.2 Real-data tab — 📝

### 7.6 Trust Layer UI (H3)
- [ ] T7.6.1 `trust/page.tsx` — ✅ Tested

### 7.7 Alerts Center
- [ ] T7.7.1 `alerts/page.tsx` — ✅ Tested

### 7.8 Dispatch Advisor (H2)
- [ ] T7.8.1 `dispatch/page.tsx` — ✅ Tested

### 7.9 What-if Simulator (H4)
- [ ] T7.9.1 `whatif/page.tsx` — ✅ Tested

### 7.10 Deviation Shield (H5)
- [ ] T7.10.1 `deviation/page.tsx` — ✅ Tested

### 7.11 Impact page
- [ ] T7.11.1 `impact/page.tsx` — ✅ Tested

### 7.12 Assumptions & provenance
- [ ] T7.12.1 `assumptions/page.tsx` — ✅ Tested

### 7.13 Polish
- [ ] T7.13.1 Visual pass — 📝
- [ ] T7.13.2 Accessibility — 📝
- [ ] T7.13.3 Lint, types, build — 📝

## Phase 8 — Integration (Day 8–9)

### 8.1 End-to-end integration
- [ ] T8.1.1 Fresh-clone run — 📝
- [ ] T8.1.2 Contract check — 📝

### 8.2 Containerization (local only)
- [ ] T8.2.1 Backend Dockerfile — 🧩 Spec code
- [ ] T8.2.2 Frontend Dockerfile — 🧩 Spec code
- [ ] T8.2.3 docker-compose — 🧩 Spec code
- [ ] T8.2.4 Run with Docker — 📝

### 8.3 Resilience
- [ ] T8.3.1 Failure keeps the last good run — 📝
- [ ] T8.3.2 Stale-data banner — 🧩 SNIPPET

### 8.4 Performance
- [ ] T8.4.1 Measure — 📝
- [ ] T8.4.2 Warm caches at startup — 📝

### 8.5 Deployment — ON HOLD until the user says "deploy"
- [ ] T8.5.1 (on hold) Choose hosts — 📝
- [ ] T8.5.2 (on hold) Configure CORS & env — 📝
- [ ] T8.5.3 (on hold) Smoke test the public URL — 📝

## Phase 9 — Docs, business case, report, demo (Day 9–10)

### 9.1 Architecture diagram
- [ ] T9.1.1 `docs/architecture.md` — 📝

### 9.2 Data assumptions
- [ ] T9.2.1 Finalise `docs/data-assumptions.md` — 📝

### 9.3 Accuracy report
- [ ] T9.3.1 Regenerate and review — 📝

### 9.4 Business case & impact
- [ ] T9.4.1 `docs/business-case.md` — 📝 [verify every market number]

### 9.5 Short report
- [ ] T9.5.1 `docs/report/report.md` → PDF — 📝

### 9.6 README
- [ ] T9.6.1 Final README — 📝

### 9.7 Pitch deck & demo script
- [ ] T9.7.1 Demo script (3 minutes) — 📝
- [ ] T9.7.2 Pitch deck — 📝

### 9.8 Final QA & release
- [ ] T9.8.1 Release checklist — 📝
- [ ] T9.8.2 Tag — 📝

---

## Hackathon requirement checklist

- [ ] Hourly forecast for the next 24–48 h (T6.2.2, T7.3.2)
- [ ] At least two models compared, simple baseline + ML (T4.8.4, T7.5.1)
- [ ] Accuracy numbers MAE & RMSE (T5.9.3, T7.5.1)
- [ ] Uncertainty band, calibrated, coverage reported (T4.7.1, T5.9.3)
- [ ] Dashboard of actual vs predicted generation (T7.4.1)
- [ ] Simple alerts for expected low/high generation (T5.3.1, T7.7.1)
- [ ] Public or synthetic generation + weather data for one site (Phases 1–2)
- [ ] Accuracy comparison with the baseline (T9.3.1)
- [ ] Dashboard and data assumptions (T7.12.1, T9.2.1)
- [ ] Architecture diagram (T9.1.1)
- [ ] Code repository (this repo)
- [ ] Short report (T9.5.1)

## Differentiators checklist

- [ ] Twin calibrated on real data: Indian plants, turbine SCADA, MP statistics (2.3–2.5)
- [ ] Benchmarks on real generation data (2.6, 2.7)
- [ ] Chronos-2 foundation model, zero-shot and LoRA fine-tuned on Kaggle (4.3, 4.4)
- [ ] Trust score validated against real errors (T5.9.2)
- [ ] Battery dispatch + value-of-forecast in MWh, ₹, tCO₂ (5.4, 5.5)
- [ ] Deviation Shield with verified CERC/MPERC rates + 96-block schedule export (5.7, T7.10.1)
- [ ] What-if simulator (5.6, T7.9.1)
- [ ] Business case with cited market numbers (T9.4.1)

## Verification items to close ([verify])

- [ ] Previous Runs API accepts start_date/end_date; model & earliest date (T1.1.1)
- [ ] Site coordinates, elevation, distance to Indore (T0.3.7)
- [ ] Kaggle R1/R2 file names, columns, units (T2.1.2, T2.1.3, T2.2.1)
- [ ] Mendeley R3 period, columns, units, licence note (T2.1.4)
- [ ] CEA monthly MP generation & capacity values (T2.1.5)
- [ ] Hub list for benchmark B (T2.7.1)
- [ ] Chronos-2 `fit` signature and checkpoint folder on Kaggle (T4.4.1, T4.4.2)
- [ ] CERC DSM formula & rates; intra-state MPERC applicability (T5.7.2)
- [ ] Market-size numbers for the business case (T9.4.1)

## Log (newest first)

| Date | Task / subphase | Note |
|---|---|---|
| 2026-10-08 | 0.2 | Python environment for ml/ completed |
| 2026-10-08 | 0.1 | Repo scaffold completed |
| 2026-10-08 | — | v3 build guide + tracker created; reference code tested on synthetic data during planning |
