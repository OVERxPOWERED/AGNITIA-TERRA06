"""Publish the live weather the app would request, for every allowlisted site, as <key>.json files.

Run by .github/workflows/prefetch-weather.yml every 30 minutes from GitHub's own network, so the deployed API
(which shares an address with many other apps and is rate-limited by Open-Meteo's free tier) reads these files
instead of calling Open-Meteo itself. Each file is {"fetched_at": epoch seconds, "payload": <Open-Meteo JSON>}
and is named by terra.data.openmeteo.payload_key(), the same function the API uses to look it up.

Usage: python scripts/prefetch_weather.py OUT_DIR
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from terra.config import load_config
from terra.data.openmeteo import FORECAST_URL, OpenMeteoClient, payload_key
from terra.data.weather_models import models_params
from terra.locations import load_locations
from terra.schema import FORECAST_VARS


def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    client = OpenMeteoClient()
    sites, _ = load_locations()
    jobs = []
    for s in sites:
        main = client.live_params(s.latitude, s.longitude, FORECAST_VARS, cfg.weather.forecast_model, 10, 3)
        jobs.append((s.id, "main", main))
        jobs.append((s.id, "models", models_params(s.latitude, s.longitude)))
    ok = failed = 0
    index = {}
    for site, kind, params in jobs:
        key = payload_key(FORECAST_URL, params)
        try:
            payload = client.get_live(FORECAST_URL, params, force=True)
            (out / f"{key}.json").write_text(json.dumps({"fetched_at": time.time(), "payload": payload}))
            index[key] = {"site": site, "kind": kind}
            ok += 1
            print(f"ok   {site:12s} {kind:6s} {key}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {site:12s} {kind:6s} {type(exc).__name__}: {exc}", file=sys.stderr)
        time.sleep(1.0)
    (out / "index.json").write_text(json.dumps({"updated": time.time(), "files": index}, indent=1))
    print(f"{ok} fetched, {failed} failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "weather-data")))
