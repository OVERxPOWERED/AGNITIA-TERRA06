---
trigger: glob
globs: backend/**
description: FastAPI backend conventions (routes, schemas, services, scheduler, tests).
---

# Backend rules

- Layering: `api/routes/*` (HTTP only) → `services/*` (orchestration) → `terra` engines (logic). Routes never contain business logic.
- Every route has Pydantic request/response models in `app/schemas/`; set `response_model`. Times in responses are ISO-8601 UTC strings; frontend converts to IST.
- Error format: `{"error": {"code": "SNAKE_CASE", "message": "human text"}}` via exception handlers.
- Contract-first: change schemas → run `make types` → update frontend. Breaking changes need a note in `.agent/context/api-contract.md`.
- Heavy work (forecast pipeline) runs in the scheduler and writes artifacts; request handlers read precomputed results. `/whatif` is the only compute-on-request route — cache by scenario hash and cap input ranges.
- Settings from env via `pydantic-settings` (`TERRA_MODE=live|replay`, `CORS_ORIGINS`, `DATA_DIR`, `ARTIFACTS_DIR`). Document every var in `.env.example`.
- Outbound HTTP: timeouts + retries; on failure serve last good run and mark it stale.
- Tests: `httpx`/`TestClient`, one test file per router; schema snapshot tests; no network in CI.
