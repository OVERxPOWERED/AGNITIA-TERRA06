# Vidyut (codebase name: TERRA) — Project Explanation

> Single source document for: user-flow / UML / DFD diagrams, tech-stack slide, PPT, feasibility report, business model.
> Written 2026-10-10 from the repo at `main` (+ uncommitted working tree) and web research. Sources are linked in §14.
> **Naming:** the code, package (`terra`), env vars (`TERRA_*`) and repo are still "TERRA"; the product/folder/roadmap say "Vidyut". Same thing.
> **Numbers rule:** every accuracy number below is the *committed real-weather* result (README / `docs/model-card.md` / `jury-evidence/`). The uncommitted working tree contains a re-run with different numbers — see §13.

---

## 1. One-paragraph summary

Vidyut is a web platform that tells a solar / wind / hybrid plant operator **how much power the plant will produce in each of the next 48 hours, how sure we are, and what to do about it** — send a schedule that avoids grid-deviation penalties, plan the battery/backup, get a WhatsApp alert when something goes wrong. It combines real weather forecasts (Open-Meteo) + a physics model of the plant + machine learning (LightGBM quantile models, with Amazon Chronos-2 as a benchmark) + a decision layer (trust score, alerts, battery dispatch LP, deviation-charge estimator, what-if simulator).

## 2. The problem

1. Solar and wind output is weather-driven and uncertain. Grid operators require generators to **commit a schedule in 15-minute blocks a day ahead** (revisable intraday) and **pay a deviation charge when actual output differs from schedule** beyond a tolerance band.
2. The rules just got much stricter. CERC's order effective **1 April 2026** tightens the revenue-neutral band from ±10% → **±5% for solar/hybrid** and ±15% → **±10% for wind**, with a phased "X-factor" (100% in FY26-27 falling to 0% by 2031) that gradually removes the cushion. It is being challenged in the Delhi High Court but is being implemented. A Grid-India study found plants spend far less time inside the tighter band (solar ~45–58%, wind ~32–73% of time). Crisil estimates unmanaged DSM exposure can cut project IRR by ~50–100 bp. States are copying (Karnataka KERC 2026: solar ±5%, wind/hybrid ±10%).
3. Forecasting in India is hard: monsoon "abrupt weather transitions", IMD base data refreshed only every ~6 h, no hyperlocal radar for RE areas (developers quoted in Reuters; even Adani Green says hyperlocal prediction is hard).
4. Small/medium plants are hit hardest: they have no in-house forecasting team, no portfolio to pool errors across, and thin margins. Bad forecasts also mean unplanned backup (fossil) use and curtailment.

## 3. The solution (what Vidyut does)

| # | Capability | What the operator gets | Built? |
|---|---|---|---|
| 1 | **48-h hourly forecast** for solar, wind and plant total, with 80% / 90% uncertainty bands | Control Room + Forecast Explorer | ✅ |
| 2 | **Trust score** per hour (0–100) | Know *which* hours to believe | ✅ |
| 3 | **Alerts** — low / high generation, ramp, low-confidence, demand shortfall, weather-disagreement | Alerts page, live via SSE, WhatsApp | ✅ |
| 4 | **Deviation Shield** — penalty estimate + 96-block (15-min) schedule CSV for the QCA | Fewer penalties | ✅ (rates illustrative) |
| 5 | **Dispatch Advisor** — LP plan for battery + backup | Less fossil backup / curtailment | ✅ |
| 6 | **What-if simulator** — change weather / battery and re-forecast | Planning | ✅ |
| 7 | **Impact** — MWh backup avoided, CO₂ avoided (CEA 0.705 t/MWh) | ESG reporting | ✅ |
| 8 | **Plant profile + setup wizard** — capacity, DC/AC, tilt, azimuth, tracking, turbine model, hub height, units out, maintenance windows, degradation, export limit | Forecast follows *your* plant | ✅ (ADR-017/018) |
| 9 | **Location page** — same plant on 8 allow-listed Indian sites, live weather | Siting / second-site view (labelled "not validated") | ✅ |
| 10 | **Measured-history upload** → calibration factor, data-quality report | Forecast tuned to *your* SCADA | ✅ (adopted only if it lowers error on last 20%) |
| 11 | **Weather second opinions** — NOAA GFS, DWD ICON (free), optional Solcast, Tomorrow.io keys | Disagreement alert when sources diverge | ✅ |
| 12 | **Deviation watch + submitted-schedule tracking** | Compare what you submitted vs. what actually happens | ✅ |
| 13 | **WhatsApp alerts** (Meta Cloud API or Twilio) | Alerts on phone | ✅ (provider keys needed) |
| 14 | **Optional login** (email + scrypt password, hashed bearer tokens) | Plant/site/calibration saved server-side | ✅ |
| 15 | Rule profiles per state, penalty simulator, charge explainer, Revision Advisor (accept/reject via WhatsApp), daily PDF report, `/jobs/tick`, rename to Vidyut | — | ❌ **Roadmap only** (`VIDYUT_ROADMAP.md` Phases 10–17, 0 tasks done) → Future scope §12 |

**Important honesty line:** Vidyut never submits to the grid. The operator sends the CSV to the SLDC through their QCA.

## 4. Target user — small & medium plants

| Segment | Size (typical) | Why they hurt | What they use today (see §14 caveats) |
|---|---|---|---|
| Independent wind/solar IPPs with 5–50 MW | 5–50 MW | Must schedule & pay DSM, or pay a QCA who passes penalties back | QCA-bundled forecast; a weather/forecast vendor; manual Excel scheduling; persistence ("same as yesterday") |
| Captive / open-access C&I plants | 1–25 MW | Need predictable green supply; penalties against open-access settlement | Often only the grid-side or QCA forecast; spreadsheets |
| Small hybrid parks (e.g. 20–90 MW) | | Two uncertain sources + storage decisions | Separate solar/wind forecasts, manual battery rules |
| QCAs / aggregators serving the above | portfolio | Carry the financial risk of members' deviations | Vendor forecasts + in-house tools |

Secondary: SLDC/DISCOM analysts (visibility), ESG teams (impact numbers). **Primary buyer = plant owner/ops manager or the QCA that serves them.**

**Who competes / what exists** (sourced examples only; I could not verify vendor lists or prices): Skymet (runs its own NWP and sells wind/solar forecasts to RE companies); del2infinity (Kolkata forecasting & scheduling service for IPPs); overseas SaaS (e.g. Ravenwits); big developers use foreign deep-learning vendors (Adani Green) or in-house control rooms; weather-data APIs (Solcast, Tomorrow.io) sell irradiance/wind data, not decisions.

## 5. What makes Vidyut different

1. **Decision-first, not forecast-only.** Forecast → trust → alert → schedule CSV → battery plan → ₹ penalty estimate in one tool.
2. **Honest uncertainty.** Calibrated bands (conformal, CQR) + a trust score whose rank-correlation with real error is measured (Spearman −0.665 solar, −0.518 wind).
3. **Plant-specific on day one without SCADA** via physics transfer, then improves when the operator uploads measured history.
4. **Multi-NWP "second opinions"** surface weather disagreement as an alert — most tools hide NWP uncertainty.
5. **Leak-free evaluation** (strict 24 h / 48 h lead mapping; no actual-weather leakage) and openly reported weaknesses.
6. **Cheap to run:** serving needs no GPU/PyTorch (Chronos-2 is benchmark-only); free-tier deployable (Render + Neon + Vercel).
7. **Built for India:** CERC DSM concepts, 15-min blocks, IST, CEA emission factor, ₹ costs.

## 6. How it works end to end

```
Open-Meteo (Previous Runs, Archive, Forecast) ─┐
NOAA GFS / DWD ICON / Solcast / Tomorrow.io ───┤
NASA POWER (irradiance cross-check) ───────────┤
Operator plant profile + measured history ─────┤
                                               ▼
  Digital twin (pvlib + windpowerlib + realism)  ──► physics prior
  34 leak-free features (fx_, phys_, cal_, hist_) ─► LightGBM quantile (5 q) ─┐
                                                      physics ────────────────┴► Ensemble + CQR bands (80/90%)
                                                                              │
              Engines: Hybrid combiner (copula) · Trust · Alerts · Dispatch LP · Deviation Shield/Watch · Impact · What-if
                                                                              │
                         FastAPI (REST + SSE) ── SQLite/Neon + Parquet run folders + model bundles
                                                                              │
                         Next.js UI (14 routes) · WhatsApp · 96-block CSV → QCA → SLDC
```

## 7. Tech stack & implementation

**Data / ML (`ml/terra`, Python ≥3.10, venv 3.12)** — pandas, numpy, scipy, pyarrow/Parquet; **pvlib** (clear-sky, PV model), **windpowerlib** (power curve MM100/2000, shear, wake 7%, electrical 2%); **LightGBM** quantile regression (q05/10/50/90/95), **Optuna** tuning (96 solar / 150 wind trials, adopted only if ≥1% pinball gain on a hold-out inside train); **conformal (CQR)** calibration; copula for hybrid band; **Chronos-2** (`amazon/chronos-2`, zero-shot with weather covariates, Kaggle 2×T4, ~87 s/source) as comparison-only; Typer CLI (`terra …`); pytest, ruff.
**Backend (`backend/app`)** — **FastAPI** + Uvicorn, **SQLModel**; **SQLite** locally / **Neon PostgreSQL** deployed; **APScheduler** (forecast job, WhatsApp monitor); **SSE** `/alerts/stream`; scrypt auth; Meta/Twilio WhatsApp; background jobs for location forecasts. Tables: `RunRow, AlertRow, UserRow, SessionRow, PlantRow, ScheduleRow, NotificationRow`. Modes: `replay` (recorded Dewas run) and `live`.
**Frontend (`frontend`)** — **Next.js 16** App Router, React 19, TypeScript, Tailwind 4, TanStack Query, ECharts, `openapi-typescript` generated types; 14 routes: `/`, `forecast, models, trust, alerts, dispatch, whatif, deviation, impact, assumptions, location, settings, setup, login`. Profile/site in `localStorage`, plus server copy when signed in.
**Infra** — Docker, `render.yaml`, Vercel, Neon, GitHub Actions (CI, weather prefetch), model bundle published as a GitHub Release zip (~12.5 MB). *Deployment status is contradictory in the docs, §13.*
**Data provenance** — weather real (Open-Meteo, CC BY 4.0, free tier is non-commercial → commercial licence needed); plant output **simulated** by a twin calibrated on Kaggle Indian solar plants, wind SCADA, CEA MP stats; demand shape from Grid-India hourly. **No real operator data yet.**

### The AI in plain words
- **Models compared (6/source):** persistence, week-mean, physics, tuned LightGBM, ensemble (served), Chronos-2 ZS (benchmark).
- **Served model:** lead-weighted blend of physics + LightGBM (solar ≈ 99% GBM), then CQR bands.
- **Leak control:** forecast features use `fx1_` (24 h-old forecast) for leads 1–24 and `fx2_` for 25–48; history lags ≥ 24·⌈lead/24⌉ h; time-based splits; `assert_no_leakage()`.
- **Trust score:** combines band width, recent residual size, lead time, etc.; thresholds for alerts are learned from the training split (P10/P25/P90/P95).

### Committed results (held-out 179 days, 2026-04-03 → 09-28, real weather, virtual plant)
| Source | Model | MAE | nMAE | Skill vs persistence | PICP80 |
|---|---|---|---|---|---|
| Solar 40 MW | Ensemble (served) | 1.57 MW | 3.9% | **+27.8%** | 91.8% all-hours / 84.8% daylight |
| Solar | Chronos-2 ZS | 1.68 | 4.2% | +22.5% | 89.4% |
| Wind 50 MW | Tuned LightGBM | 3.99 | 8.0% | **+38.3%** | 76.8% |
| Wind | Chronos-2 ZS | 4.05 (lowest RMSE 5.94) | 8.1% | +37.4% | 74.6% |
| Wind | Ensemble (served) | 4.15 | 8.3% | +35.8% | 72.6% |
Business numbers (illustrative DSM rates, 179 days, vs persistence): ₹29.9 lakh backup cost saved, ₹1.11 crore DSM charge saved, 304.7 MWh backup & 248.9 MWh curtailment avoided, 214.8 tCO₂ avoided.
**Known weaknesses (disclosed):** wind coverage below nominal (calibrated on dry winter, tested on monsoon); wind ensemble worse than standalone GBM; physics-twin truth means skill may differ on real SCADA.

## 8. User flow (for the user-flow diagram)

1. Open dashboard (public; default = recorded Dewas replay) →
2. *(optional)* Sign up / log in →
3. **Setup wizard**: plant name & type, capacity, solar layout, turbine model/hub height, units out & maintenance windows, grid export limit, WhatsApp number →
4. *(optional)* **Upload measured history** CSV → data-quality report → calibration factor adopted or rejected →
5. **Location**: pick site → background live forecast job (progress) →
6. **Control Room**: combined band, trust ribbon, demand gap, alerts banner →
7. **Forecast / Models / Trust** drill-down →
8. **Alerts**: acknowledge; SSE push; WhatsApp message (≤10/day) →
9. **Dispatch** (battery/backup plan) and **What-if** (change scenario) →
10. **Deviation Shield**: view penalty estimate → download 96-block CSV → *operator sends to QCA → SLDC* → record submitted schedule →
11. **Deviation watch**: compare submitted schedule with new forecasts → warning/WhatsApp →
12. **Impact / Assumptions** for reporting.

## 9. Diagram seed lists

**Actors:** Plant Operator; QCA; SLDC / Grid-India; Admin/Developer. **External systems:** Open-Meteo, NOAA GFS, DWD ICON, NASA POWER, Solcast*, Tomorrow.io*, Meta WhatsApp Cloud / Twilio, GitHub Actions/Releases, Kaggle (GPU, offline). (*optional)
**Use cases:** view forecast; assess trust; receive/ack alerts; plan battery; run what-if; estimate penalty; export schedule; configure plant; upload history; compare weather sources; sign in; manage WhatsApp; retrain models (offline, dev).
**DFD Level 0:** Operator ↔ Vidyut ↔ {Weather providers, WhatsApp provider, QCA (via CSV)}.
**DFD Level 1 processes:** P1 Ingest weather · P2 Build features/twin · P3 Forecast (GBM+physics+CQR) · P4 Apply plant profile & calibration · P5 Engines (trust, alerts, dispatch, DSM, impact, what-if) · P6 Serve API/SSE · P7 Notify · P8 Auth & profile.
**Data stores:** D1 SQLite/Neon (runs, alerts, users, sessions, plants, schedules, notifications); D2 Parquet run folders (`artifacts/runs/<ts>`, `LATEST`); D3 model bundles (`artifacts/models/*/bundle`); D4 evaluation/backtests; D5 config YAML (site, dsm, locations, calibration, gbm_params); D6 weather cache (disk + 20-min live cache).
**Main classes (UML):** `TerraConfig`, `PlantProfile`, `ForecastBundle`, `Ensemble`, `GbmQuantile`, `ConformalCalibrator`, `Chronos2Runner`, `TrustEngine`, `AlertEngine`, `DispatchLP`, `DsmEngine`, `DeviationWatch`, `WhatIf`; backend `Settings`, `RunRow, AlertRow, UserRow, SessionRow, PlantRow, ScheduleRow, NotificationRow`, routers `account, alerts, assumptions, dispatch, dsm, forecast, health, impact, locations, models, whatif`.
**Sequence to draw:** Live forecast — UI → `POST /locations/{id}/forecast` → job → weather fetch (+second opinions) → bundle predict → profile transfer → engines → result → UI polls `/locations/jobs/{id}/result`.

## 10. Business model

### Business Model Canvas (hypotheses)
- **Segments:** small/medium solar, wind, hybrid IPPs; captive/open-access C&I; QCAs.
- **Value:** lower DSM penalties, calibrated confidence, one-click schedule CSV, battery/backup plan, WhatsApp alerts, ESG impact.
- **Channels:** direct sales to plant managers; QCA partnerships; pilots in Dewas/Omkareshwar belt; webinars on the 2026 DSM change.
- **Relationships:** onboarding wizard + pilot support; monthly accuracy report.
- **Revenue:** SaaS per MW/month (repo hypothesis ₹5,000/MW/month; API tier ₹50,000/site/month — *unvalidated*); gain-share on penalties saved (option); QCA white-label.
- **Resources:** models, twin, data pipeline, 2 developers.
- **Activities:** forecasting ops, model retraining, plant onboarding, regulatory tracking.
- **Partners:** QCAs, weather vendors (Open-Meteo commercial, Solcast, Tomorrow.io), WhatsApp BSP, cloud hosts, inverter/SCADA vendors.
- **Costs:** weather licences, cloud, WhatsApp messages, sales/support, regulatory/legal.

### Lean Canvas
Problem: DSM penalties, poor local forecasts, no decision tooling for small plants. Customer: 5–50 MW plants. UVP: "Know the next 48 hours *and* what to do about it." Solution: §3. Channels/Revenue/Costs as above. Key metrics: MAE/nMAE vs persistence, % blocks inside band, ₹ penalty saved/MW, alert precision, weekly active plants. Unfair advantage: calibrated trust + plant-specific calibration data accumulates with each customer. Unvalidated assumption to test first: *will a plant pay for forecasts that beat their QCA's?*

### SWOT
- **S:** leak-free honest evaluation; full decision stack; low serving cost; multi-NWP; physics + ML.
- **W:** trained/tested on a *simulated* plant; no real SCADA; wind coverage gap; DSM rates illustrative; single home site; 2-person team; Open-Meteo free tier non-commercial.
- **O:** April 2026 band tightening; state regulators copying; pooling/aggregation demand; storage & hybrid growth; Indian vendors weak on hyperlocal.
- **T:** regulatory reversal (Delhi HC); incumbent QCAs/vendors (Skymet etc.); big developers' in-house AI; weather-data licence cost; trust barrier for a new vendor.

### Advantages / disadvantages / limitations
**Advantages:** cheaper than bespoke vendor engagements (hypothesis), explainable, runs on free tier, self-serve onboarding, transparent accuracy.
**Disadvantages:** forecast quality bounded by NWP (ECMWF IFS 0.25°, ~hourly, no on-site sensors yet); no direct SLDC/QCA integration; extra tool to learn.
**Limitations (technical):** hourly resolution (15-min downscaled synthetically); 48 h horizon; capacity-scaling assumes same technology mix; non-Dewas sites unvalidated; accuracy numbers come from a virtual plant; Chronos-2 not served; no password reset; DSM formula/rates must be verified before external use; replay mode default.

### Feasibility (TELOS outline)
- **Technical:** ✅ working end-to-end, tests present (ML + backend), free-tier deployable. Risk: real-data generalisation.
- **Economic:** low run cost; revenue unproven; weather licence is the main fixed cost. Do a 3-IPP pilot to validate price.
- **Legal:** DSM/state rules vary and change; Open-Meteo commercial licence required; data-protection for operator SCADA; WhatsApp business policies; vendor must not claim grid submission.
- **Operational:** needs hourly job reliability, retraining cadence, support; 2-person team is thin.
- **Schedule:** pilot-ready in weeks if real SCADA is available; roadmap Phases 10–17 estimated ~6 days by the repo's own plan.

### PPT skeleton (12 slides)
1 Title · 2 Problem (April 2026 DSM, numbers) · 3 Who hurts (small/medium plants) · 4 Today's alternatives · 5 Vidyut solution (6 features) · 6 Demo flow (§8) · 7 AI & architecture (§6–7) · 8 Results (table §7) · 9 Impact (₹, MWh, CO₂) · 10 Business model + pricing hypothesis · 11 Risks & limits (honest) · 12 Roadmap & ask. (Existing: `docs/TERRA_SIH_Pitch.pptx`, `docs/pitch-deck-outline.md`.)

## 11. Where to push accuracy (ranked by evidence in this repo)

Evidence: Chronos-2 zero-shot (a big foundation model) did **not** beat tuned LightGBM (solar 1.68 vs 1.57 MW; wind 4.05 vs 3.99 MW MAE), so *a bigger model alone is not the main lever*; the dominant error source is the weather forecast (physics-only model is poor; GBM learns corrections from `fx_ws100`, `fx_ghi`).

1. **Real SCADA / measured history** instead of the twin (biggest credibility + accuracy gain; target variable becomes real, residual features `hist_resid_*` become meaningful).
2. **Better weather input:** feed GFS/ICON/Solcast/Tomorrow.io (already fetched as "second opinions") as **model features / multi-NWP ensemble**, add on-site met mast, cloud-motion/satellite nowcasts (intraday), higher-resolution NWP (e.g. 3 km regional models if licensed).
3. **Rolling / season-aware conformal recalibration** (fixes wind coverage 72–77% → ~80%) and **seasonal blend weights** (fixes wind ensemble worse than GBM).
4. **More history & features:** >2 yrs of data, turbine wake/direction sectors, ramp-event features, 15-min native targets, per-turbine SCADA availability.
5. **Model upgrades:** Chronos-2 **LoRA fine-tune** on plant data (planned in ADR-005, never run); try TimesFM-2.5 / Moirai-2 / TiRex as extra benchmarks; stacked ensemble (GBM + Chronos + physics) with learned weights; quantile NN (TFT/N-HiTS); larger Chronos with fine-tuning. Expect gains mainly after real data exists.
6. **Operational:** hourly refresh with latest NWP cycle (shortens effective lead → large gain vs fixed 24/48 h), automatic retraining, drift monitoring.
7. **Evaluate by what matters:** optimise the DSM ₹ loss (asymmetric quantile choice per block) and report % blocks inside ±5%/±10%, not only MAE.

## 12. Future scope
Phases 10–17 of `VIDYUT_ROADMAP.md`: rename to Vidyut, solar-only/wind-only plant types, state rule profiles (CERC 2026, Gujarat, MP), charge explanation, penalty simulator, **Revision Advisor** (accept/reject via dashboard or WhatsApp `YES/NO code`, revision counter, event log), daily PDF report, setup wizard 2.0, `/jobs/tick` cron, retrain button. Beyond: SCADA connectors, QCA/SLDC API export, pooling across plants, market (IEX) bidding support, storage co-optimisation, mobile app, multilingual UI.

## 13. Doc audit — what was stale or contradictory
See the chat summary delivered with this file; short list: (a) working-tree evaluation outputs differ from every published doc; (b) docs lacked profile/login/WhatsApp/second-opinion/location features; (c) `architecture.md` said 10 pages; (d) `api-contract.md` missed ~20 endpoints; (e) "deployment deferred" vs roadmap "deployed"; (f) `handoff.md`/`known-issues.md` outdated; (g) naming TERRA vs Vidyut.

## 14. Sources
- CERC phased X-factor / bands from 1 Apr 2026: [Energetica India](https://www.energetica-india.net/news/cerc-notifies-phased-x-factor-reduction-for-wind-and-solar-tightens-deviation-bands-from-april-2026), [SolarQuarter](https://solarquarter.com/2026/04/01/cerc-announces-phased-dsm-reform-for-wind-and-solar-tightens-deviation-norms-by-2031/), [PSU Watch (Delhi HC)](https://psuwatch.com/newsupdates/cerc-tightens-dsm-for-wind-and-solar-generators-writ-petitions-challenge-order-in-delhi-hc)
- Karnataka KERC 2026: [SolarQuarter](https://solarquarter.com/2026/06/24/kerc-notifies-dsm-regulations-2026-tightens-forecasting-norms-for-solar-wind-and-hybrid-projects-in-karnataka/)
- Developer forecasting pain (Reuters via MarketScreener): [article](https://www.marketscreener.com/news/india-s-clean-energy-firms-seek-better-weather-data-as-rules-tighten-ce7d51dedc8af327)
- Wind viability under DSM: [S&P Global](https://www.spglobal.com/esg/s1/research-analysis/indias-new-dsm-regulations-wind-plants-may-become-unviable.html); QCA role (AP 2016 regs summary): [SlideShare](https://www.slideshare.net/slideshow/andhra-pradesh-electricity-regulatory-commission-forecasting-scheduling-deviation-settlement-and-related-matters-of-solar-and-wind-generation-sources-regulations-2016/65885739)
- Vendors: [Skymet](https://en.wikipedia.org/wiki/Skymet_Weather_Services), [Ravenwits](https://windletteren.substack.com/p/rawenwits-renewable-energy-generation-forecast-ia)
- Chronos-2: [paper](https://arxiv.org/abs/2510.15821)
- Market scale: [Renewable energy in India (Wikipedia)](https://en.wikipedia.org/wiki/Renewable_energy_in_India) — no reliable small-plant segment figure found; treat TAM as unknown.
**Gaps I could not verify from the web:** what small plants actually pay QCAs/vendors; current QCA fee models; final CERC formula/rates (the repo's rates are marked illustrative); the reported "Third Amendment, 31 Aug 2026" (single trade-press mention).
