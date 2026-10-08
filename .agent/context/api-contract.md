# API contract (planned — freeze by end of Day 5, roadmap 6.1)

Base URL: `http://localhost:8000`. JSON. Times ISO-8601 UTC. Errors: `{"error": {"code", "message"}}`. Source of truth once built: FastAPI `/openapi.json` → `frontend/src/lib/api/schema.d.ts` (`make types`).

| Method | Path | Params | Returns |
|---|---|---|---|
| GET | `/health` | — | status, version, git_sha, mode, data_freshness |
| GET | `/site` | — | site, plant, battery config summary |
| GET | `/forecast` | `source=solar\|wind\|hybrid`, `horizon=48`, `model=ensemble` | issue_time, series[{target_time, lead_h, q05…q95, trust_score}] |
| GET | `/forecast/history` | `source`, `start`, `end`, `model` | series with `actual_mw` + quantiles |
| GET | `/models/compare` | `source`, `dataset=twin\|real`, `split=test` | rows per model: mae, rmse, nmae, skill, picp80, mpiw80 |
| GET | `/metrics` | `model`, `source`, `slice=lead\|hour\|month` | sliced metrics |
| GET | `/trust` | `source` | per-hour score, colour, reason |
| GET | `/alerts` | `active=true`, `since` | alert objects (see data-contracts) |
| GET | `/alerts/stream` | — | SSE: `alert`, `run_complete` events |
| GET | `/dispatch` | `strategy=advisor\|rule\|none` | schedule[{t, charge_mw, discharge_mw, soc_mwh, backup_mw, curtail_mw}], kpis |
| GET | `/value-of-forecast` | — | table per forecast model: backup_mwh, cost_inr, tco2 |
| POST | `/whatif` | scenario {cloud_mult, irr_scale, wind_scale, solar_mw, wind_mw, batt_mw, batt_mwh, tracker} | before/after forecast + dispatch KPIs |
| GET | `/dsm/summary` | `start`, `end` | deviation %, charges ₹ by strategy, `illustrative` flag |
| GET | `/dsm/schedule.csv` | `date` | 96-block schedule CSV |
| GET | `/impact` | — | co2_avoided_t, backup_avoided_mwh, inr_saved, curtail_avoided_mwh, sources |
| GET | `/assumptions` | — | data card + provenance (markdown/JSON) |
| GET | `/calibration` | — | calibration results/plots metadata |

Change log: (empty — record breaking changes here)
