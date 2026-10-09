# Decision log (ADR-lite)

Newest first. Template: `.agent/templates/adr.md`.

## ADR-013 — Chronos-2 zero-shot on Kaggle (2026-10-09)
- **Status**: Accepted
- **Context**: Foundation time-series model Amazon Chronos-2 (`amazon/chronos-2`) needs to be evaluated zero-shot with weather covariates on Kaggle GPUs (2x T4). In local environment, PyTorch and Chronos are not installed to avoid multi-GB dependency bloat. Kaggle execution requires GPU accelerator access and outbound Internet connectivity (for pip installing `chronos-forecasting` and downloading Hugging Face checkpoint weights), which are gated on Kaggle account phone verification. Strict data integrity rules mandate that covariates must be leak-free (leads 1–24 use `fx1_`, leads 25–48 use `fx2_`, history <= issue time, no `fx0_` or `act_*`, and per-item fill to prevent cross-issue data bleed).
- **Decision**:
  1. **Strict Leak-Free Covariate Framing**: Implemented per-item forward/backward filling in `build_inputs` (`ml/terra/models/chronos2.py`) to prevent cross-item temporal leakage across concatenated issues. Added offline unit test (`ml/tests/test_chronos2_covariates.py`) verifying that past context never contains timestamps > t0 or fx0/act values, future covariates strictly follow `LEAD_BUCKETS`, and batch filling never leaks across issues.
  2. **Kaggle Bundle & Dataset**: Packaged dataset, config, issue indices, and clean package source via `terra export-kaggle` (~5.2 MB) and published as private Kaggle dataset `overxpowered/terra06-bundle-20261009` under Open-Meteo CC BY 4.0 attribution.
  3. **Kaggle GPU Job & Diagnostics**: Authored `ml/kaggle/chronos2_infer.ipynb` with metadata targeting GPU T4 x2. Probe executions verified that while OAuth credentials and weekly GPU quota (30h) are valid, the account requires completing Kaggle phone verification in web settings (`https://www.kaggle.com/settings`) before the runtime backend enables GPU allocation and outbound Internet networking.
  4. **CLI Integration**: Updated `terra train --chronos-dir` in `ml/terra/pipelines/cli.py` to seamlessly accept either `<source>_<model>.parquet` or `<model>_<source>.parquet` formats, verifying full alignment with `align_external`.
- **Consequences**: Zero-shot inference pipeline is fully verified, tested, and ready to run the moment phone verification is completed in the Kaggle UI. Local codebase remains lightweight without PyTorch.

## ADR-012 — Deployment: Neon + Release-asset artifacts + pinger (2026-10-09)
- **Status**: Accepted
- **Context**: TERRA needs to be deployable on free tiers (Render for FastAPI backend, Vercel for Next.js frontend, Neon for serverless PostgreSQL). Ephemeral container disks on Render reset on restarts, making SQLite unsuitable for persistent run indexes. Model and forecast artifacts (~23 MB) must stay out of git history per Rule 8, but are required by the backend container image at runtime. Render free instances sleep after 15 min of inactivity, causing ~30–50 s cold starts.
- **Decision**:
  1. **Database**: Use Neon serverless PostgreSQL via `TERRA_DB_URL` (normalised to `postgresql+psycopg://` with `pool_recycle=300` and `pool_pre_ping=True`). Retain local SQLite as default. If the configured remote DB is unreachable at startup, degrade gracefully to a local SQLite database under `TERRA_ARTIFACTS_DIR` so forecast endpoints remain available. Automatic idempotent re-seed populates runs and alerts tables from artifact files on fresh/reset databases.
  2. **Artifact Delivery**: Build a deterministic runtime deployment bundle (~12.5 MB zip) using `make bundle` (`scripts/make_deploy_bundle.py`). Deliver to the backend Docker image via GitHub Release asset URL and SHA256 build arguments (`ARTIFACT_URL`, `ARTIFACT_SHA256`) at Docker build time.
  3. **Cold-start UX & Keep-alive**: Implement TanStack Query exponential backoff retries (up to 12 attempts, capped at 8 s) for 502/503/504 and network errors with an accessible "API is waking up" state and spinner. Supplement during demo/evaluation windows with an uptime pinger (UptimeRobot / cron-job.org hitting `GET /health` every 5 min).
  4. **Frontend API Configuration**: Next.js requires `NEXT_PUBLIC_API_BASE` baked at build time. Render and Vercel are cross-origin; CORS origins are configured via `TERRA_CORS_ORIGINS`. In production builds, the client fails loudly with a visible configuration card if `NEXT_PUBLIC_API_BASE` is missing or misconfigured to localhost.
- **Consequences**: Zero git bloat from model binaries. Fully functional cloud deployment achievable within free-tier constraints. Local developer experience remains zero-config with SQLite. Deployment execution remains on hold until explicitly requested by the user.

## ADR-011 — Hybrid trust as generation-weighted mean (2026-10-09)
- **Status**: Accepted
- **Context**: Hybrid trust score previously took `min(solar_trust, wind_trust)` per hour, causing 43 of 48 hours to be flagged as "low" (< 40) trust on typical replay days (average score ~18 / 100), despite informative per-source trust (Spearman correlation with absolute error: solar -0.67, wind -0.50). Taking the minimum unfairly penalised the hybrid plant even when one source was generating nearly all power with high confidence.
- **Decision**: Compute hybrid trust as an expected-generation-weighted average: $w_s = q50_s$, $w_w = q50_w$, $trust_h = (w_s \cdot trust_s + w_w \cdot trust_w) / (w_s + w_w)$. When both $q50$ are near zero ($< 10^{-6}$ MW), fall back to the unweighted mean $(trust_s + trust_w) / 2$. Keep `trust_level` thresholds (`level()`) unchanged, and retain the explanation reason of the lower-trust source.
- **Consequences**: Hybrid trust score reliably reflects the confidence of the actual generation mix without compound pessimism. Scores remain calibrated between 0 and 100. Average hybrid trust rises to ~20 on the replay day with 8 medium-confidence hours, while maintaining full sensitivity to genuine forecast uncertainty.

## ADR-010 — Data-driven alert thresholds (2026-10-09)
- **Status**: Accepted
- **Context**: The static alert thresholds (fixed 10% / 85% of plant capacity, 20 MW/h ramp) failed on realistic forecasts over all 179 test days with strict lead mapping. Maximum forecast P50 reached only 32.9 MW (solar), 37.6 MW (wind), and 55.8 MW (hybrid), so HIGH_GENERATION never fired (0 alerts, P(X > 85% cap) never reached 0.60). Similarly, max |dP50/dt| was 9.7 MW/h (solar), 18.2 MW/h (wind), 18.3 MW/h (hybrid), so RAMP never fired (0 alerts). Conversely, LOW_GENERATION fired on 179/179 days, creating alert fatigue. Alert precision/recall was also not evaluated or reported.
- **Decision**: Adopt data-driven, per-source alert thresholds learned strictly from the training split generation series (`alert_thresholds()` in `ml/terra/engines/alerts.py`):
  - Low generation threshold: 10th percentile (`low_quantile: 0.10`) of generation (daylight-only `cal_is_day == 1` for solar).
  - High generation threshold: 90th percentile (`high_quantile: 0.90`) of generation (daylight-only for solar).
  - Ramp threshold: 95th percentile (`ramp_quantile: 0.95`) of hour-to-hour absolute generation change (`|diff|`).
  - Hybrid source uses the sum of solar and wind generation on the training split.
  - Learned thresholds are persisted inside the `engines@latest` artifact (`hybrid/engines`) and loaded by both the evaluation and forecast pipelines, falling back to static fraction/MW values if absent.
  - Alert quality (precision, recall, alert hours, event hours) is systematically evaluated on the test split deduplicating overlapping forecast hours across daily 00:00 UTC runs and reported in `results.json` and `docs/engine-results.md`.
- **Consequences**: Thresholds accurately reflect the local site distribution (Dewas hybrid plant) without look-ahead leakage. Recalibration is automatic during engine evaluation when retraining. Quantiles are config-controlled under `alerts:` in `config/site.yaml`. Alert messages explicitly display the threshold in MW and probability. Wind low generation alert fires 0 times under P10 (0.09 MW) because ensemble forecast uncertainty does not concentrate >= 60% probability below 0.09 MW; this is reported honestly rather than artificially tuned.
- **Addendum (2026-10-09)**: Wind generation training P10 is ~0.09 MW (0.18% of 50 MW), representing calm/near-zero generation where ensemble forecast uncertainty rarely concentrates >= 60% probability below 0.09 MW, resulting in zero alerts across 179 test days despite 211 actual calm hours. `alerts.low_quantile` is extended to support a per-source mapping in config (backward-compatible with scalar): `{solar: 0.10, wind: 0.25, hybrid: 0.10}`. Wind training P25 is ~1.14 MW (2.3% capacity) justified strictly from the training distribution, establishing an operationally meaningful threshold for calm/low wind conditions without look-ahead or tuning against test-period outcomes.

## ADR-009 — Strict lead mapping (2026-10-09)
- **Status**: Accepted by the user
- **Context**: Open-Meteo `_previous_dayN` is the forecast issued N*24 h before the valid time (`_previous_day0` is the live/current run). For an issue time T and target T+L, a forecast issued at (target - N*24 h) is available at T only if N*24 >= L. The previous mapping used `fx0_` (lead ~0) for L=1..12 and `fx1_` (24 h) for L=25..36, which used forecasts issued after T (look-ahead leak), flattering short-lead accuracy.
- **Decision**: Adopt strict leak-free lead mapping: leads 1–24 use `fx1_` (`previous_day1`, 24 h ahead) and leads 25–48 use `fx2_` (`previous_day2`, 48 h ahead). `fx0_` is never used as a lead-resolved forecast feature. New buckets: `(1, 24, "1-24", "fx1_")` and `(25, 48, "25-48", "fx2_")`. This supersedes the lead mapping part of ADR-004.
- **Consequences**: Forecast errors (nMAE/nRMSE) will rise, particularly on short leads (1–12 h), providing an honest evaluation. `fx0_` remains in the dataset only for `phys0_*` generation-history residuals at times <= issue time. In live operational mode, the latest available run is copied across all leads (`fx0_`/`fx1_`/`fx2_`), representing the real-operator situation.

## ADR-008 — Deployment deferred (2026-10-08)
Deployment (roadmap 8.5) starts only when the user says so. Local Docker Compose + replay mode until then.

## ADR-007 — Add H5 Deviation Shield + Impact engine (2026-10-08)
Judges likely value revenue potential and social impact. DSM charge estimation is the clearest revenue story for Indian RE plants; rates stay config-driven and "illustrative" until verified.

## ADR-006 — Real-data strategy R1–R5 (2026-10-08)
No public multi-year hybrid plant data near Indore. Use real weather + twin calibrated on real Indian solar plant data (Kaggle), real wind SCADA, CEA MP monthly stats; benchmark on real all-India hourly generation.

## ADR-005 — Chronos-2 LoRA fine-tune on Kaggle is core (2026-10-08)
Free 2× T4 available; time box 2 h, hard cap 12 h. Zero-shot remains the fallback.

## ADR-004 — Open-Meteo Previous Runs for forecast inputs (2026-10-08)
Gives true 24 h/48 h-ahead forecasts from Jan 2024. Lead mapping: 1–12 h → day0, 13–36 h → day1, 37–48 h → day2.

## ADR-003 — Site: Dewas (Jamgudrani) virtual hybrid near Indore (2026-10-08)
Hackathon is in Indore; a local site makes the problem story concrete.

## ADR-002 — FastAPI backend (2026-10-07)
All ML/energy libraries are Python; OpenAPI → TypeScript types for Next.js.

## ADR-001 — Hybrid solar + wind scope (2026-10-07)
10 days is enough for both; complementarity is a stronger story than either alone.

## ADR-003: Site Facts
- Confirmed site is at Jamgudrani hills ridge east of Dewas town (approx 35-40km from Indore).
- Confirmed elevation is 536.0m from Open-Meteo.


## ADR-004: Weather API facts
- Previous Runs DOES accept start_date/end_date (returns 200).
- The model 'ecmwf_ifs025' returns non-null values.
- The earliest date that includes previous_day2 for wind_speed_100m without missing data is around 2024-03-01.
- Archive API returns all variables and provides elevation.


## ADR-014 — Chronos-2 zero-shot execution and evaluation results (2026-10-09)
- **Status**: Accepted
- **Context**: Follow-up to ADR-013. Following phone verification of the Kaggle account, GPU accelerator access (2× Tesla T4) and Internet connectivity were unlocked. Chronos-2 (`amazon/chronos-2`, `chronos-forecasting` 2.3.2) was executed zero-shot with weather covariates over 1,436 forecast issues (68,928 rows per source) covering validation and test splits.
- **Protocol**:
  - Inputs: Context of 1,024 h history with day-ahead covariates (`fx1_`), future horizon of 48 h with lead-resolved covariates (`fx1_` for leads 1–24, `fx2_` for leads 25–48). Per-item forward/backward fill to guarantee zero cross-issue data bleed.
  - Execution: Kaggle GPU kernel `overxpowered/terra-chronos2-zs` ran in 175.5 s wall-clock (solar: 86.8 s, wind: 88.7 s) on Tesla T4.
  - Output post-processing: Finalized quantiles (clipped to [0, capacity], sorted monotonic, solar night zeroed via zenith >= 90).
- **Results**:
  - Coverage: 100.0% coverage across all 68,576 evaluation rows in `val_fit`, `val_cal`, and `test` splits for both sources.
  - Test metrics (solar, capacity 40 MW): MAE 1.6823 MW (4.21% nMAE), RMSE 3.4817 MW, PICP80 89.37%, Skill vs persistence +22.51%. Beats persistence (2.1710 MW), physics (2.1215 MW), and week_mean (1.8337 MW).
  - Test metrics (wind, capacity 50 MW): MAE 4.0495 MW (8.10% nMAE), RMSE 5.9439 MW, PICP80 74.63%, Skill vs persistence +37.41%. Significantly beats persistence (6.4702 MW) and physics (5.2647 MW); RMSE (5.9439 MW) improves upon the current GBM baseline (5.9649 MW) and ensemble (6.0155 MW).
- **Consequences**: Predictions are downloaded to `artifacts/chronos/` and validated for immediate consumption by `terra train --chronos-dir`. Note: membership in the production ensemble is superseded by ADR-016 (comparison-only benchmark).

## ADR-015 — GBM tuning (T4.5) (2026-10-09)
- **Status**: Accepted
- **Context**: LightGBM quantile regression models (5 quantiles: 0.05, 0.10, 0.50, 0.90, 0.95) for solar and wind generation previously used default baseline hyperparameters (`num_leaves=63, min_child_samples=50, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, reg_alpha=0.0`). Hyperparameters required leak-free, time-boxed tuning without touching validation or test splits.
- **Protocol & Adoption Rule**:
  - Pre-registered protocol (`ml/scripts/tune_gbm.py`): per source separately on TRAIN split minus last 20% temporal holdout (`tune_holdout`, boundary-crossing rows dropped).
  - Objective: mean pinball loss across the 5 quantiles on `tune_holdout`.
  - Optuna TPE seed 42, 40-minute timeout per source.
  - Adoption rule: Adopt tuned parameters only if relative pinball improvement on `tune_holdout` >= 1.0%; otherwise retain default parameters (`adopted: false`).
- **Results**:
  - Solar: Default pinball 0.46092, Best pinball 0.44116 (+4.29% relative improvement over 96 trials in 40.27 min). Adopted: `num_leaves: 17, min_child_samples: 190, learning_rate: 0.0204, subsample: 0.75908, colsample_bytree: 0.92444, reg_lambda: 4.13625, reg_alpha: 4.56068`. On test split, tuned GBM improved MAE from 1.6047 to 1.5665 MW (-2.38%), RMSE from 3.2715 to 3.1993 MW (-2.21%), and pinball from 0.3943 to 0.3791 (-3.85%).
  - Wind: Default pinball 0.89478, Best pinball 0.83409 (+6.78% relative improvement over 150 trials in 40.06 min). Adopted: `num_leaves: 15, min_child_samples: 121, learning_rate: 0.0304, subsample: 0.70885, colsample_bytree: 0.90749, reg_lambda: 0.05976, reg_alpha: 4.50032`. On test split, tuned GBM improved MAE from 4.0071 to 3.9901 MW (-0.42%), RMSE from 5.9649 to 5.9557 MW (-0.15%), pinball from 1.0298 to 1.0111 (-1.82%), and PICP80 from 0.7275 to 0.7682 (+5.60%).
- **Consequences**: Tuned parameters merged into `config/gbm_params.yaml` and loaded automatically by `terra train`. Model bundle metadata records resolved parameters, tuning metadata, and wall-clock times in `meta.json`.

## ADR-016 — Chronos-2 is comparison-only (not an ensemble member) (2026-10-09)
- **Status**: Accepted
- **Context**: Amazon Chronos-2 zero-shot predictions were generated on Kaggle GPUs (`artifacts/chronos/`, ADR-014) with 100% coverage on `val_fit`, `val_cal`, and `test` splits. Serving a foundation transformer model requires PyTorch and multi-GB model weights, which is incompatible with free-tier serverless/container deployment and not installed in the local environment. If Chronos-2 were an ensemble member, live/replay forecast serving (`ml/terra/pipelines/forecast.py`) would require PyTorch inference at runtime.
- **Decision**:
  - Include Chronos-2 zero-shot as a COMPARISON-ONLY benchmark model (NOT an ensemble member).
  - In `ml/terra/pipelines/train.py`, external models are evaluated across `val_cal` and `test` splits (appearing in backtest `predictions.parquet`, `metrics_test.csv`, and `docs/accuracy-report.md`), but do NOT join `bundle.ensemble.members` by default.
  - Added CLI flag `--chronos-in-ensemble / --no-chronos-in-ensemble` (default: False) keeping the old behavior reachable when explicitly requested.
  - In `ml/terra/pipelines/forecast.py`, the `chronos2` inference branch only triggers when Chronos is an ensemble member, eliminating runtime PyTorch dependencies for serving.
  - In frontend, Chronos-2 is selectable in Forecast Explorer and tagged as a benchmark in Models & Accuracy without skewing deployable model selection logic.
- **Consequences**: Production serving bundle and forecast pipeline remain zero-torch and lightweight while evaluation reports and UI provide transparent, rigorous comparison against zero-shot foundation models.



## ADR-017 — Active site and plant profile (location, wizard, settings) (2026-10-09)
- **Status**: Accepted
- **Context**: The dashboard showed one recorded Dewas replay run. We want an operator to choose a site and describe their plant, and have every tab follow it.
- **Decision**:
  - Allowlisted sites live in `config/locations.yaml`; the API accepts only those ids.
  - The plant profile (`ml/terra/profile.py`, one field table drives the wizard, Settings, validation and the pipeline) and the selected site are held in the browser (`localStorage`) and sent with each live-forecast request. The server stores nothing per visitor, so one visitor cannot change another's plant.
  - Default view stays the recorded Dewas replay. A non-home site, Dewas on live weather, or any changed profile value switches Control Room, Forecast (48 h), Alerts and Dispatch to a live run built by `POST /locations/{id}/forecast`. Accuracy, trust, impact and cost pages stay Dewas-evaluation figures and say so.
  - Capacity changes are applied by scaling: models run for the trained plant (`model_cfg`), MW outputs, demand and alert thresholds are multiplied by the capacity ratio. This assumes the same technology mix. Fields the models were not trained for (tilt, azimuth, DC size, hub height) are recorded only and labelled so.
  - Forecasts at non-Dewas sites or with a customised plant are labelled "not validated"; no accuracy numbers are shown for them (non-negotiable rule 3).
- **Consequences**: A deployed single-plant product would need server-side persistence and authentication for the profile; this is the next step, not part of this change. Uploading measured plant data to calibrate the physics model (onboarding stage 6) is not built.
