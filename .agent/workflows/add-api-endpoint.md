---
description: Add or change a FastAPI endpoint contract-first and regenerate frontend types.
---

# Add an API endpoint

1. Define request/response Pydantic models in `backend/app/schemas/<area>.py`.
2. Add the route in `backend/app/api/routes/<area>.py` (HTTP only) and register the router in `main.py`.
3. Implement logic in `backend/app/services/<area>.py`, calling `terra` engines/artifacts.
4. Add a fixture-backed test in `backend/tests/test_<area>.py` (status, schema, edge cases).
5. Update `.agent/context/api-contract.md` (route, params, response summary).
6. Run `make types`; fix frontend compile errors; add/adjust the TanStack Query hook in `frontend/src/hooks/`.
