# Architecture

See `ROADMAP.md` §3 for the Mermaid diagram (source of truth). Summary:

```
Open-Meteo (Previous Runs, Archive, Forecast) ─┐
Real datasets (R1–R5) ──► calibration ─────────┤
                                               ▼
                 ml/terra/data  → digital twin (pvlib, windpowerlib, realism) → dataset.parquet
                 ml/terra/features → framing (issue_time, lead_h) + features
                 ml/terra/models → M0, M1, M2, M3, M3-FT → ensemble → CQR
                 ml/terra/engines → hybrid, trust, alerts, dispatch, value_of_forecast, whatif, dsm, impact
                 ml/terra/pipelines → train.py, forecast.py, cli.py
                                               ▼
backend/app: scheduler (hourly forecast run) → artifacts + SQLite → REST/SSE (FastAPI)
                                               ▼
frontend (Next.js): Control Room, Forecast, Models, Trust, Alerts, Dispatch, What-if, Deviation Shield, Impact, Assumptions
```

## Directory map
| Path | Purpose |
|---|---|
| `config/site.yaml` | site, plant, battery, demand, costs, alerts, splits, weather settings |
| `config/dsm.yaml` | DSM tolerance bands, X-factor, charge slabs (`verify` flags) |
| `config/calibration/*.yaml` | parameters fitted in Phase 2 |
| `ml/terra/data/` | Open-Meteo client, weather tables, twins, realism, demand, dataset build, quality |
| `ml/terra/real/` | real dataset loaders, calibration, real-data benchmarks |
| `ml/terra/features/` | framing, feature builder, clear-sky |
| `ml/terra/models/` | base interface, baselines, physics, gbm, chronos2, ensemble, conformal, downscale, registry |
| `ml/terra/eval/` | metrics, backtest, report |
| `ml/terra/engines/` | hero-feature logic (pure Python) |
| `ml/kaggle/` | GPU notebooks |
| `backend/app/` | FastAPI: routes, schemas, services, db, scheduler |
| `frontend/src/` | Next.js app, components, hooks, generated API types |
| `data/` | raw/external/interim/processed (gitignored), `samples/` committed |
| `artifacts/` | trained models, backtests, forecast runs (gitignored) |
| `docs/` | assumptions, model card, reports, business case, images |

## Runtime flow (live/replay)
1. Scheduler (hourly) → `pipelines/forecast.py` with issue_time = now (live) or virtual now (replay).
2. Fetch forecast weather (live) or read recorded (replay) → features → models → ensemble → CQR.
3. Engines produce hybrid, trust, alerts, dispatch, dsm, impact.
4. Results saved to `artifacts/runs/<issue_time>/` + DB; SSE notifies clients.
5. API serves the latest run; `/whatif` computes on request with cache.
