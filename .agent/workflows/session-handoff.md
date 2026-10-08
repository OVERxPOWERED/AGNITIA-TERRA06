---
description: Update the handoff memory at the end of a work session so the next human or agent can continue.
---

# Session handoff

Rewrite (don't append forever) `.agent/memory/handoff.md` sections:
1. **Snapshot** — date/time (IST), branch, last commit SHA, overall progress `x / 77`.
2. **Done this session** — subphases and notable changes.
3. **In progress** — subphase, what's left, exact next command.
4. **Next up** — the next 3 subphases in order per the ROADMAP schedule.
5. **Blockers / questions for the user**.
6. **Gotchas** — anything surprising (move durable ones to `known-issues.md`).
Keep it under ~80 lines.
