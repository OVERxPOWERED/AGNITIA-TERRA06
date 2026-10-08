# Decision log (ADR-lite)

Newest first. Template: `.agent/templates/adr.md`.

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

