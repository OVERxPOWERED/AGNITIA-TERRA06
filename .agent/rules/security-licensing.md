---
trigger: model_decision
description: Apply when adding dependencies, datasets, external APIs, credentials, or public-facing claims.
---

# Security & licensing rules

- Secrets only in env vars / local files listed in `.gitignore`. Provide `.env.example` with dummy values.
- Datasets: record source URL, licence, download date and citation in `data/external/<name>/README.md`. Don't commit raw third-party data; commit only derived small samples if the licence allows.
- Open-Meteo: free tier is non-commercial and CC BY 4.0 — attribution required; note commercial plan need in the business case.
- Chronos-2 is Apache-2.0; pvlib BSD-3; windpowerlib MIT. Check licence of any new dependency (avoid GPL in the backend if possible).
- Public claims (pitch, README, UI): cite sources for regulations, emission factors and plant facts; mark estimates and extrapolations as such.
- Validate and bound all API inputs (`/whatif` ranges, date windows).
