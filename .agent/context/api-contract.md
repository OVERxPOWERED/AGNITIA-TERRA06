# API contract (final)

Base URL: `http://localhost:8000`. JSON. Times ISO-8601 UTC. Errors: `{"error": {"code", "message"}}`, with `503 NO_DATA_YET` when a run or evaluation does not exist yet. Source of truth: FastAPI `/openapi.json` → `frontend/src/lib/api/schema.d.ts` (`make types`).

| Method | Path | Params | Response model |
|---|---|---|---|
| GET | `/health` | — | `Health` |
| GET | `/site` | — | `SiteInfo` |
| GET | `/forecast` | `source=solar\|wind\|hybrid`, `horizon=1..48` | `ForecastResponse` |
| GET | `/forecast/history` | `source=solar\|wind`, `model`, `start`, `end`, `lead_h_max` | `HistoryResponse` (test-split actual vs predicted) |
| GET | `/models/compare` | `source`, `split=val_cal\|test`, `by=lead_bucket` | `ModelsResponse` |
| GET | `/alerts` | `active_after` | `AlertOut[]` |
| POST | `/alerts/{id}/ack` | — | `{ok}` |
| GET | `/alerts/stream` | — | SSE events `run_complete`, `alert`, `ping` |
| GET | `/dispatch` | `strategy=advisor\|rule\|none` | `DispatchResponse` |
| POST | `/whatif` | body `WhatIfRequest` | `WhatIfResponse` |
| GET | `/dsm/summary` | — | `DsmSummary` |
| GET | `/dsm/schedule.csv` | `source` | CSV text (96 blocks, IST) |
| GET | `/impact` | — | `ImpactResponse` (impact + value-of-forecast + hybrid stats) |
| GET | `/assumptions` | — | markdown strings of the three data docs |
| GET | `/trust` | — | trust evidence per source |

Change log:
- Updated to match implemented endpoints in T6.1.2
