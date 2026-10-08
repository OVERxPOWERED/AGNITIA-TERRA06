---
trigger: model_decision
description: Apply when committing, branching, opening PRs, or updating COMPLETION.md / handoff.
---

# Git & progress rules

- `main` must always run. Branch `feat/<subphase>-<slug>`; merge when tests pass.
- Commit format `<area>(<subphase>): <imperative summary>`; areas: ml, backend, frontend, docs, config, ci, agent.
- Do not commit: `.env`, `kaggle.json`, `data/**` (except READMEs/samples), `artifacts/**`, `node_modules`, `.next`.
- After finishing a subphase: tick it in `COMPLETION.md`, update the phase count and total, add a log line, update `.agent/memory/handoff.md`. Same commit as the work or an immediate follow-up `docs(<id>): mark complete`.
- Never mark `[x]` if the *Done when* check has not actually been run.
- Never force-push `main`.
