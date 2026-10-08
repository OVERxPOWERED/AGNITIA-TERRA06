# Decision log (ADR-lite)

Newest first. Template: `.agent/templates/adr.md`.

## ADR-008 — Deployment deferred (2026-10-08)
Deployment (roadmap 8.5) starts only when the user says so. Local Docker Compose + replay mode until then.

## ADR-007 — Add H5 Deviation Shield + Impact engine (2026-10-08)
Judges likely value revenue potential and social impact. DSM charge estimation is the clearest revenue story for Indian RE plants; rates stay config-driven and "illustrative" until verified.

## ADR-006 — Real-data strategy R1–R5 (2026-10-08)
No public multi-year hybrid plant data near Indore. Use real weather + twin calibrated on real Indian solar plant data (Kaggle), real wind SCADA, CEA MP monthly stats; benchmark on real all-India hourly generation.

## ADR-005 — Chronos-2 LoRA fine-tune on Kaggle is core (2026-10-08)
Free 2× T4 available; time box 2 h, hard cap 12 h. Zero-shot remains the fallback.

## ADR-004 — Open-Meteo Previous Runs for forecast inputs (2026-10-08)
Gives true 24 h/48 h-ahead forecasts from Jan 2024. Lead mapping: 1–12 h → day0, 13–36 h → day1, 37–48 h → day2.

## ADR-003 — Site: Dewas (Jamgudrani) virtual hybrid near Indore (2026-10-08)
Hackathon is in Indore; a local site makes the problem story concrete.

## ADR-002 — FastAPI backend (2026-10-07)
All ML/energy libraries are Python; OpenAPI → TypeScript types for Next.js.

## ADR-001 — Hybrid solar + wind scope (2026-10-07)
10 days is enough for both; complementarity is a stronger story than either alone.

## ADR-003: Site Facts
- Confirmed site is at Jamgudrani hills ridge east of Dewas town (approx 35-40km from Indore).
- Confirmed elevation is 536.0m from Open-Meteo.

