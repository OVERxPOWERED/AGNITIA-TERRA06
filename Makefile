# TERRA — one command per task. Recipe lines MUST start with a TAB character.
# Use the project virtualenv when it exists, so commands work without activating it (any shell, fish included).
BIN := $(if $(wildcard $(CURDIR)/.venv/bin/python),$(CURDIR)/.venv/bin/,)
PY ?= $(BIN)python
ML_ENV = cd ml &&
API_ENV = cd backend &&

.PHONY: setup setup-ml setup-backend setup-web data data-synthetic frame calibrate real-benchmark train evaluate \
        report forecast demo-synthetic api web test test-ml test-backend lint types export-kaggle clean-artifacts bundle

setup: setup-ml setup-backend setup-web

setup-ml:
	$(PY) -m pip install -e "ml[dev,tune,real]"

setup-backend:
	$(PY) -m pip install -e "backend[dev]"

setup-web:
	cd frontend && npm install

data:            ## real weather (needs internet) -> dataset
	$(BIN)terra fetch-weather && $(BIN)terra build-dataset

data-synthetic:  ## offline development only — never report these numbers
	$(BIN)terra build-dataset --synthetic

frame:
	$(BIN)terra frame

calibrate:
	$(BIN)terra calibrate

real-benchmark:
	$(BIN)terra real-benchmark

train: frame
	$(BIN)terra train $(if $(CHRONOS),--chronos-dir $(CHRONOS),)

evaluate:
	$(BIN)terra evaluate

report:
	$(BIN)terra report

forecast:
	$(BIN)terra forecast --mode $(or $(MODE),replay)

demo-synthetic: data-synthetic train evaluate report forecast  ## full offline pipeline in ~3 min

api:
	$(API_ENV) $(BIN)uvicorn app.main:app --reload --port 8000

web:
	cd frontend && NEXT_PUBLIC_API_BASE=$(or $(API),http://localhost:8000) npm run dev   ## API=https://... to use another backend

test: test-ml test-backend

test-ml:
	$(ML_ENV) $(BIN)pytest -q

test-backend:
	$(API_ENV) TERRA_SCHEDULER_ENABLED=false $(BIN)pytest -q

lint:
	$(BIN)ruff check ml backend
	cd frontend && npm run lint && npx tsc --noEmit

types:           ## regenerate frontend/src/lib/api/schema.d.ts from the FastAPI OpenAPI schema (no server needed)
	$(API_ENV) TERRA_SCHEDULER_ENABLED=false $(PY) -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../frontend/openapi.json
	cd frontend && npx openapi-typescript openapi.json -o src/lib/api/schema.d.ts

export-kaggle:
	$(BIN)terra export-kaggle

clean-artifacts:
	rm -rf artifacts/models artifacts/backtests artifacts/evaluation artifacts/runs

bundle:          ## package runtime artifacts into dist/ for deployment release
	$(PY) scripts/make_deploy_bundle.py
