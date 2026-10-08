---
description: Fetch and cache Open-Meteo weather (previous runs + archive) for the configured site.
---

# Fetch weather data

1. Confirm `config/site.yaml` site coordinates, weather model, variables and date span.
2. `make data` (or `python -m terra.pipelines.cli fetch-weather --start ... --end ...`).
3. The client chunks by month and caches to `data/raw/openmeteo/`. Re-runs must not hit the network for cached chunks.
4. Check `data/interim/gap_report.csv`; investigate any column with > 1% missing.
5. Respect free-tier limits (600/min, 5,000/h, 10,000/day). If you get HTTP 429, wait — don't loop.
6. Never commit downloaded data.
