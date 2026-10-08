# TERRA — one command per task. Recipe lines MUST start with a TAB character.
PY ?= python
ML_ENV = cd ml &&
API_ENV = cd backend &&

.PHONY: setup setup-ml setup-backend setup-web data data-synthetic frame calibrate real-benchmark train evaluate \
        report forecast demo-synthetic api web test test-ml test-backend lint types export-kaggle clean-artifacts

setup: setup-ml setup-backend setup-web

setup-ml:
	$(PY) -m pip install -e "ml[dev,tune,real]"

setup-backend:
	$(PY) -m pip install -e "backend[dev]"

setup-web:
	cd frontend && npm install

data:            ## real weather (needs internet) -> dataset
	terra fetch-weather && terra build-dataset

data-synthetic:  ## offline development only — never report these numbers
	terra build-dataset --synthetic

frame:
	terra frame

calibrate:
	terra calibrate

real-benchmark:
	terra real-benchmark

train: frame
	terra train $(if $(CHRONOS),--chronos-dir $(CHRONOS),)

evaluate:
	terra evaluate

report:
	terra report

forecast:
	terra forecast --mode $(or $(MODE),replay)

demo-synthetic: data-synthetic train evaluate report forecast  ## full offline pipeline in ~3 min

api:
	$(API_ENV) uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test: test-ml test-backend

test-ml:
	$(ML_ENV) pytest -q

test-backend:
	$(API_ENV) TERRA_SCHEDULER_ENABLED=false pytest -q

lint:
	ruff check ml backend
	cd frontend && npm run lint && npx tsc --noEmit

types:           ## regenerate frontend/src/lib/api/schema.d.ts from the FastAPI OpenAPI schema (no server needed)
	$(API_ENV) TERRA_SCHEDULER_ENABLED=false $(PY) -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../frontend/openapi.json
	cd frontend && npx openapi-typescript openapi.json -o src/lib/api/schema.d.ts

export-kaggle:
	terra export-kaggle

clean-artifacts:
	rm -rf artifacts/models artifacts/backtests artifacts/evaluation artifacts/runs
