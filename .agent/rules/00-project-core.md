---
trigger: always_on
description: Core non-negotiable rules for the TERRA forecasting project.
---

# Core rules (always on)

- Work maps to a subphase in `ROADMAP.md`; tick it in `COMPLETION.md` only when its *Done when* passes (workflow: `finish-subphase`).
- **No leakage:** features = forecast weather (`fx*`) + calendar/solar geometry + generation observed ≤ issue time. Never `act_*` columns. Time-based splits only.
- **No hand-typed metrics** — numbers come from `ml/terra/eval/`.
- **Provenance honesty:** virtual plant at a real location, calibrated on real data. Unverified rates/rules carry `verify: true` and an "illustrative" label.
- Time is `ts_utc` (tz-aware UTC) internally; IST (`Asia/Kolkata`) only for display.
- Units: MW / MWh / W/m² / m/s / °C / hPa / ₹. Suffix names when ambiguous.
- All assumptions in `config/*.yaml`; no magic numbers in code.
- Credit "Weather data by Open-Meteo.com (CC BY 4.0)" wherever weather-derived data appears.
- No secrets, raw data, or model binaries in git.
- Training jobs < 12 h (planned ≤ 2 h); log wall-clock time.
- Deployment is on hold until the user says "deploy".
- Prefer small, reviewable commits: `<area>(<subphase>): <summary>`.
- When unsure about scope or a decision, ask the user rather than guessing.
