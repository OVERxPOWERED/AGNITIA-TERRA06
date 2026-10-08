---
description: Begin work on a roadmap subphase (e.g. /start-subphase 1.4).
---

# Start a subphase

1. Read `.agent/memory/handoff.md` and `.agent/memory/known-issues.md`.
2. Open `ROADMAP.md`, find the subphase ID; read *What / Where / Why / Steps / Done when*.
3. Check `COMPLETION.md`: confirm dependencies (earlier subphases it relies on) are `[x]`. If not, tell the user which are missing.
4. Read the matching rules in `.agent/rules/` and context files (`data-contracts.md`, `api-contract.md`, `architecture.md`).
5. Create a branch `feat/<id>-<slug>` from `main`.
6. Mark the subphase `[~]` in `COMPLETION.md`.
7. Write a short plan (3–8 bullets) mapping the roadmap *Steps* to files; flag any [verify] items you must resolve first.
8. Implement step by step; run tests after each meaningful step.
