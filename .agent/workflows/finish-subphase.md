---
description: Close a subphase after its Done-when check passes and update tracking files.
---

# Finish a subphase

1. Run the *Done when* check from `ROADMAP.md` literally (tests, command, metric). Paste the result into your summary.
2. Run `make lint` and `make test` (or the area-specific equivalents).
3. Update `COMPLETION.md`:
   - `[~]` → `[x]` for the subphase
   - Phase row `Done / Total` and the **Total** row
   - "Last updated" line
   - New log row at the top: `| YYYY-MM-DD | <id> | <one-line outcome + key number> |`
   - Tick any hackathon/differentiator checklist items now satisfied
4. If a decision changed, add an ADR in `.agent/context/decisions.md` and a line in the ROADMAP changelog.
5. Update `.agent/memory/handoff.md` (workflow `session-handoff`).
6. Commit: `<area>(<id>): <summary>`; merge to `main` when CI passes.
