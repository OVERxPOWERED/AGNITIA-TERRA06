# VIDYUT_COMPLETION.md — tracker for VIDYUT_ROADMAP.md (Phases 10–17)

Tick a box when the task's **Check** passes. Same IDs as the roadmap. Status legend in the roadmap §F.

## Progress

| Phase | Tasks | Done |
|---|---|---|
| 10 — Rename TERRA → Vidyut (Day 1) | 17 | 0 |
| 11 — Plant types: solar-only, wind-only, hybrid (Day 1–2) | 23 | 0 |
| 12 — Decision engines: rule profiles, charges, simulator, revisions, report (Day 2) | 24 | 0 |
| 13 — Backend: operator workflow, reports, setup and notifications API (Day 3–4) | 20 | 0 |
| 14 — Frontend: Revisions & Log, simulator, charge explanation, report, setup, settings (Day 2–4) | 16 | 0 |
| 15 — WhatsApp alerts for the operator (Day 4) | 12 | 0 |
| 16 — Production: artifacts, hourly refresh, environment, retrain (Day 5) | 13 | 0 |
| 17 — Integration, docs and demo (Day 5–6) | 9 | 0 |

## Definition of done for this phase set

- [ ] Rename complete; old artifacts and TERRA_* env vars still work; migrated bundle deployed
- [ ] Solar-only, wind-only and hybrid plants each work end to end (wizard → pages → report)
- [ ] Rule profiles: CERC 2026, Gujarat (verified), MP (verified or clearly labelled unverified)
- [ ] Penalty simulator and charge explanation on Deviation Shield
- [ ] Revision Advisor: recommendation → accept/reject (dashboard and WhatsApp) → Rev n → event log
- [ ] Daily report on screen and as PDF
- [ ] Production: hourly tick, state survives a redeploy, memory within 512 MB
- [ ] WhatsApp live with the Twilio sandbox for both team phones
- [ ] Docs, Q&A and a rehearsed 6-minute demo + fallback video

## Phase 10 — Rename TERRA → Vidyut (Day 1)

### 10.1 Run the rename
- [ ] **T10.1.1** — Prepare a clean branch
- [ ] **T10.1.2** — Add the rename script
- [ ] **T10.1.3** — Dry run, then run

### 10.2 Compatibility layer
- [ ] **T10.2.1** — `ml/vidyut/compat.py`
- [ ] **T10.2.2** — `ml/vidyut/__init__.py`
- [ ] **T10.2.3** — `ml/vidyut/models/registry.py` (fallback load + migration)
- [ ] **T10.2.4** — CLI command `vidyut migrate-artifacts`
- [ ] **T10.2.5** — Backend accepts old variable names
- [ ] **T10.2.6** — Ruff knows both package names
- [ ] **T10.2.7** — Re-install the packages

### 10.3 Verify and migrate the artifacts
- [ ] **T10.3.1** — Tests, lint, build
- [ ] **T10.3.2** — Migrate local artifacts once
- [ ] **T10.3.3** — Merge

### 10.4 Deployment after the rename
- [ ] **T10.4.1** — Nothing breaks on deploy
- [ ] **T10.4.2** — Rename the Render variables (tidy-up, any time)
- [ ] **T10.4.3** — Do NOT rename the GitHub repo or the Render service during the hackathon
- [ ] **T10.4.4** — Record the decision

## Phase 11 — Plant types: solar-only, wind-only, hybrid (Day 1–2)

### 11.1 Two-layer configuration
- [ ] **T11.1.1** — `ml/vidyut/config.py`
- [ ] **T11.1.2** — Ignore the operator overlay

### 11.2 Reference → plant mapping
- [ ] **T11.2.1** — `ml/vidyut/plant.py`
- [ ] **T11.2.2** — Tests for plant types, overlay, mapping and the rename shim

### 11.3 Forecast pipeline per plant type
- [ ] **T11.3.1** — `ml/vidyut/pipelines/forecast.py`
- [ ] **T11.3.2** — Try all three plant types

### 11.4 What-if per plant type
- [ ] **T11.4.1** — `ml/vidyut/engines/whatif.py`

### 11.5 Backend: serve only the plant's series
- [ ] **T11.5.1** — `backend/app/services/plant.py`
- [ ] **T11.5.2** — `backend/app/schemas/api.py`
- [ ] **T11.5.3** — `backend/app/api/routes/health.py`
- [ ] **T11.5.4** — `backend/app/api/routes/forecast.py`
- [ ] **T11.5.5** — `backend/app/services/runs.py`
- [ ] **T11.5.6** — `backend/app/services/whatif.py`
- [ ] **T11.5.7** — Two one-line route fixes

### 11.6 Frontend: pages follow the plant type
- [ ] **T11.6.1** — Regenerate API types
- [ ] **T11.6.2** — `frontend/src/hooks/plant.ts`
- [ ] **T11.6.3** — `frontend/src/components/ui/SourceToggle.tsx`
- [ ] **T11.6.4** — `frontend/src/hooks/api.ts`
- [ ] **T11.6.5** — Control Room `frontend/src/app/page.tsx`
- [ ] **T11.6.6** — Forecast Explorer `frontend/src/app/forecast/page.tsx`
- [ ] **T11.6.7** — Models & Accuracy `frontend/src/app/models/page.tsx`
- [ ] **T11.6.8** — Trust `frontend/src/app/trust/page.tsx`
- [ ] **T11.6.9** — What-if `frontend/src/app/whatif/page.tsx`

## Phase 12 — Decision engines: rule profiles, charges, simulator, revisions, report (Day 2)

### 12.1 State rule profiles
- [ ] **T12.1.1** — `config/rules/cerc_2026.yaml`
- [ ] **T12.1.2** — `config/rules/gujarat_gerc_2019.yaml`
- [ ] **T12.1.3** — `config/rules/madhya_pradesh_mperc_2018.yaml`
- [ ] **T12.1.4** — `config/rules/_template.yaml` (how to add a state)
- [ ] **T12.1.5** — `ml/vidyut/rules.py`
- [ ] **T12.1.6** — Remove the old DSM file
- [ ] **T12.1.7** — Verify the Madhya Pradesh bands (research task, ~2 h)

### 12.2 Deviation charges v2 and charge explanation
- [ ] **T12.2.1** — `ml/vidyut/engines/dsm.py`
- [ ] **T12.2.2** — Rule and explanation tests
- [ ] **T12.2.3** — Update the engine tests for the new DSM signature

### 12.3 Penalty simulator engine
- [ ] **T12.3.1** — `ml/vidyut/engines/penalty_sim.py`

### 12.4 Revision Advisor engine
- [ ] **T12.4.1** — `ml/vidyut/engines/revision.py`
- [ ] **T12.4.2** — Revision tests

### 12.5 Training and evaluation for single-source plants + rule-aware DSM evaluation
- [ ] **T12.5.1** — Small edits in three files
- [ ] **T12.5.2** — `ml/vidyut/engines/value_of_forecast.py` (adds `total_long`)
- [ ] **T12.5.3** — `ml/vidyut/engines/impact.py`
- [ ] **T12.5.4** — `ml/vidyut/pipelines/cli.py`
- [ ] **T12.5.5** — `ml/vidyut/pipelines/evaluate.py`
- [ ] **T12.5.6** — Run it
- [ ] **T12.5.7** — Prove a solar-only retrain works (into a scratch folder)

### 12.6 Daily report engine and PDF
- [ ] **T12.6.1** — Add `reportlab` to `ml/pyproject.toml`
- [ ] **T12.6.2** — `ml/vidyut/engines/daily_report.py`
- [ ] **T12.6.3** — `ml/vidyut/eval/pdf.py`
- [ ] **T12.6.4** — Simulator and report tests

## Phase 13 — Backend: operator workflow, reports, setup and notifications API (Day 3–4)

### 13.1 Dependencies and settings
- [ ] **T13.1.1** — `backend/pyproject.toml`
- [ ] **T13.1.2** — `backend/app/settings.py`
- [ ] **T13.1.3** — `backend/.env.example`

### 13.2 Database tables
- [ ] **T13.2.1** — `backend/app/db/models.py`

### 13.3 Services
- [ ] **T13.3.1** — `backend/app/services/jobs.py`
- [ ] **T13.3.2** — `backend/app/scheduler.py`
- [ ] **T13.3.3** — `backend/app/services/schedule.py`
- [ ] **T13.3.4** — `backend/app/services/notify.py`
- [ ] **T13.3.5** — `backend/app/services/reports.py`
- [ ] **T13.3.6** — `backend/app/services/setup.py`

### 13.4 Routes
- [ ] **T13.4.1** — `backend/app/api/routes/workflow.py`
- [ ] **T13.4.2** — `backend/app/api/routes/jobs.py`
- [ ] **T13.4.3** — `backend/app/api/routes/dsm.py` (profiles, explain, simulate)
- [ ] **T13.4.4** — `backend/app/api/routes/reports.py`
- [ ] **T13.4.5** — `backend/app/api/routes/setup.py`
- [ ] **T13.4.6** — `backend/app/api/routes/notify.py` (contacts, test message, webhooks)
- [ ] **T13.4.7** — `backend/app/main.py`

### 13.5 Tests
- [ ] **T13.5.1** — `backend/tests/test_workflow.py`
- [ ] **T13.5.2** — Run everything
- [ ] **T13.5.3** — Click through the API

## Phase 14 — Frontend: Revisions & Log, simulator, charge explanation, report, setup, settings (Day 2–4)

### 14.1 Types, hooks, navigation
- [ ] **T14.1.1** — `frontend/src/lib/api/workflow.ts`
- [ ] **T14.1.2** — `frontend/src/hooks/workflow.ts`
- [ ] **T14.1.3** — `frontend/src/components/shell/nav.ts`
- [ ] **T14.1.4** — Page titles

### 14.2 Deviation Shield: simulator + charge explanation
- [ ] **T14.2.1** — `frontend/src/components/workflow/ChargeExplainer.tsx`
- [ ] **T14.2.2** — `frontend/src/components/workflow/PenaltySimulator.tsx`
- [ ] **T14.2.3** — `frontend/src/app/deviation/page.tsx`

### 14.3 Revisions & Log
- [ ] **T14.3.1** — `frontend/src/components/workflow/RecommendationCard.tsx`
- [ ] **T14.3.2** — `frontend/src/components/workflow/EventLog.tsx`
- [ ] **T14.3.3** — `frontend/src/app/revisions/page.tsx`

### 14.4 Daily Report
- [ ] **T14.4.1** — `frontend/src/app/reports/page.tsx`

### 14.5 Plant setup wizard
- [ ] **T14.5.1** — `frontend/src/app/setup/page.tsx`

### 14.6 Settings
- [ ] **T14.6.1** — `frontend/src/app/settings/page.tsx`

### 14.7 App shell
- [ ] **T14.7.1** — `frontend/src/components/shell/AppShell.tsx`

### 14.8 Frontend checks
- [ ] **T14.8.1** — Static checks
- [ ] **T14.8.2** — Browser walk-through (fresh database)

## Phase 15 — WhatsApp alerts for the operator (Day 4)

### 15.1 Twilio WhatsApp Sandbox (hackathon)
- [ ] **T15.1.1** — Create the account and open the sandbox
- [ ] **T15.1.2** — Join from every phone that should receive messages
- [ ] **T15.1.3** — Make the API reachable for replies
- [ ] **T15.1.4** — Configure Vidyut
- [ ] **T15.1.5** — Point the sandbox at the webhook
- [ ] **T15.1.6** — Test end to end

### 15.2 Meta WhatsApp Cloud API (production path, optional)
- [ ] **T15.2.1** — App and number
- [ ] **T15.2.2** — Create the two templates
- [ ] **T15.2.3** — Configure Vidyut
- [ ] **T15.2.4** — Webhook
- [ ] **T15.2.5** — Test

### 15.3 Safety and compliance checklist
- [ ] **T15.3.1** — Go through the checklist

## Phase 16 — Production: artifacts, hourly refresh, environment, retrain (Day 5)

### 16.0 Light re-tune for rule changes
- [ ] **T16.0.1** — `evaluate_dsm` + `retune_dsm` in `ml/vidyut/pipelines/evaluate.py`

### 16.1 New artifact bundle with replay data
- [ ] **T16.1.1** — `scripts/make_deploy_bundle.py`
- [ ] **T16.1.2** — `deploy/artifacts.lock`
- [ ] **T16.1.3** — `backend/Dockerfile`
- [ ] **T16.1.4** — `.dockerignore`: never ship a local plant overlay
- [ ] **T16.1.5** — Build, publish, point the lock at it

### 16.2 Render environment
- [ ] **T16.2.1** — `render.yaml`
- [ ] **T16.2.2** — Set the values in the Render dashboard

### 16.3 Hourly refresh from GitHub Actions
- [ ] **T16.3.1** — `.github/workflows/tick.yml`
- [ ] **T16.3.2** — Secrets and first run

### 16.4 CI
- [ ] **T16.4.1** — Keep CI green

### 16.5 One-click retrain on GitHub Actions (stretch)
- [ ] **T16.5.1** — `.github/workflows/retrain.yml`
- [ ] **T16.5.2** — Enable it

## Phase 17 — Integration, docs and demo (Day 5–6)

### 17.1 End-to-end checks
- [ ] **T17.1.1** — Local full run
- [ ] **T17.1.2** — Three plant types on the deployed site
- [ ] **T17.1.3** — Restart survival
- [ ] **T17.1.4** — WhatsApp rehearsal

### 17.2 Documentation
- [ ] **T17.2.1** — Update the narrative docs
- [ ] **T17.2.2** — Judge Q&A additions (EXPLAIN.md or pitch notes)
- [ ] **T17.2.3** — Find out who reads the report

### 17.3 Demo
- [ ] **T17.3.1** — Demo script (6 minutes)
- [ ] **T17.3.2** — Fallback

## Log

| Date | Task | Who | Note |
|---|---|---|---|
| | | | |
