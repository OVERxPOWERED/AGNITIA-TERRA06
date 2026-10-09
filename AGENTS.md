# AGENTS.md — AGNITIA TERRA06

Instructions for AI coding agents (Claude Code, Codex, Cursor, Copilot, Gemini CLI, Antigravity, etc.) and humans working in this repo. Keep this file short; details live in [`.agent/`](./.agent/README.md).

## What this project is

**TERRA** — a hybrid solar + wind generation forecasting platform for a virtual co-located plant in the Dewas wind belt near Indore, Madhya Pradesh. It forecasts hourly generation for the next 24–48 h, compares a simple baseline against ML models (LightGBM quantile, Chronos-2), shows MAE/RMSE and a calibrated uncertainty band, raises low/high generation alerts, plans battery/backup dispatch, and estimates deviation (DSM) charges. Built for a 10-day hackathon by 2 developers.

- Plan: [`ROADMAP.md`](./ROADMAP.md) (phases → subphases with *Steps* and *Done when*)
- Build guide: [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) · tracker: [IMPLEMENTATION_COMPLETION.md](./IMPLEMENTATION_COMPLETION.md)
- Progress: [`COMPLETION.md`](./COMPLETION.md)
- Current state & next steps: [`.agent/memory/handoff.md`](./.agent/memory/handoff.md)
- Decisions: [`.agent/context/decisions.md`](./.agent/context/decisions.md)

## Stack

| Area | Tech | Location |
|---|---|---|
| Data/ML | Python 3.11, pandas, pyarrow, LightGBM, pvlib, windpowerlib, chronos-forecasting (Chronos-2), scipy | `ml/terra/` |
| Backend | FastAPI, Pydantic v2, SQLModel (SQLite), APScheduler, SSE | `backend/app/` |
| Frontend | Next.js (App Router) + TypeScript, Tailwind, shadcn/ui, ECharts, TanStack Query | `frontend/src/` |
| Config | YAML validated by Pydantic | `config/` |
| GPU jobs | Kaggle notebooks (2× T4) | `ml/kaggle/` |

## Commands

```bash
make setup      # install ml, backend, frontend deps
make data       # fetch/cache weather, build digital-twin dataset
make calibrate  # real-data calibration (Phase 2)
make train      # train models, write artifacts/
make backtest   # evaluate on validation/test, write docs/ results
make forecast   # run one live (or replay) forecast pipeline
make api        # uvicorn backend on :8000
make web        # next dev on :3000
make test       # all tests (no network)
make lint       # ruff + eslint + tsc
make types      # regenerate frontend API types from OpenAPI
```
If a target does not exist yet, it belongs to subphase 0.6 — create it there, don't invent ad-hoc scripts.

## How to work (every task)

1. Find the subphase in `IMPLEMENTATION_ROADMAP.md` that the task belongs to. If none fits, ask the user or add it to the roadmap **and** `COMPLETION.md` with the same ID.
2. Read `.agent/memory/handoff.md` and the relevant `.agent/rules/*` and `.agent/context/*` files.
3. Follow the subphase *Steps*. Small commits, one concern each.
4. Run tests and lint for the area you touched.
5. When *Done when* passes: follow `.agent/workflows/finish-subphase.md` (tick `COMPLETION.md`, log line, update handoff).

## Non-negotiable rules

1. **No data leakage.** Model features may use only forecast weather (`fx*`), deterministic calendar/solar-geometry features, and generation observed at or before the issue time. Never use `act_*` (actual weather) columns as features. Time-based splits only — never shuffle.
2. **Never hand-type metrics.** Every number in docs/UI/report comes from the evaluation harness (`ml/terra/eval/`).
3. **Be honest about data provenance.** The plant is a *virtual digital twin at a real location*, calibrated on real data. Never claim it is a real operator's data. Unverified regulatory/cost numbers carry `verify: true` in config and an "illustrative" label in the UI.
4. **UTC inside, IST for display.** Store `ts_utc` (tz-aware); convert to `Asia/Kolkata` only in presentation.
5. **Units in names where ambiguous** (`_mw`, `_mwh`, `_wm2`). Power in MW, energy in MWh.
6. **Config, not constants.** Plant, battery, thresholds, DSM rules, costs live in `config/*.yaml`.
7. **Attribution.** Show "Weather data by Open-Meteo.com (CC BY 4.0)" wherever weather-derived data is displayed.
8. **No secrets or large data in git.** `.env`, `kaggle.json`, raw/processed data and model artifacts are gitignored. Model artifacts stay out of git history; a versioned GitHub Release asset is the supported delivery channel for deployment.
9. **Training budget.** Any training/fine-tuning job must stay under 12 hours; planned budget is ≤ 2 h per job. Log wall-clock time in the artifact `meta.json`.
10. **Deployment is on hold** until the user explicitly says to deploy (roadmap 8.5).
11. **Don't rewrite the roadmap silently.** Changes to scope/decisions go in `ROADMAP.md` changelog and `.agent/context/decisions.md`.

## Git

- Default branch `main` must stay runnable. Feature branches: `feat/<subphase-id>-<slug>` (e.g. `feat/1.4-solar-twin`).
- Commit messages: `<area>(<subphase>): <imperative summary>` — e.g. `ml(1.4): add pvlib solar twin`.
- Commit identity for this repo: `overpowered <6burhanuddin6@gmail.com>` unless the developer's own identity is configured.

## Where things go

See `.agent/context/architecture.md` for the full tree. Quick map:
- New data source → `ml/terra/data/` (weather/twin) or `ml/terra/real/` (real plant data)
- New model → `ml/terra/models/` implementing `models/base.py` interface (`.agent/workflows/add-model.md`)
- New engine (alerts, dispatch, DSM…) → `ml/terra/engines/` (pure Python, no web code)
- New endpoint → `backend/app/api/routes/` + schema + service (`.agent/workflows/add-api-endpoint.md`)
- New page → `frontend/src/app/<route>/` (`.agent/workflows/add-frontend-page.md`)
- Exploration → `notebooks/` (never imported by package code)
