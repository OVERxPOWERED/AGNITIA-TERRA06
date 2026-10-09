"""Open-Meteo client with monthly chunking, on-disk cache, retries and rate limiting.

APIs used
- Previous Runs  https://previous-runs-api.open-meteo.com/v1/forecast  -> forecast weather fx0/fx1/fx2
- Archive        https://archive-api.open-meteo.com/v1/archive         -> actual weather act_
- Forecast       https://api.open-meteo.com/v1/forecast                -> live forecast (platform runtime)

Licence: Open-Meteo data is CC BY 4.0; free tier is non-commercial. Always show ATTRIBUTION.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from terra.logs import get_logger
from terra.paths import DATA_RAW
from terra.schema import OPENMETEO_VARS

log = get_logger(__name__)

LIVE_TTL_S = 20 * 60          # live forecasts change a few times a day; one request per place per 20 minutes
LIVE_STALE_S = 4 * 3600       # how old an answer may be when Open-Meteo is refusing requests
_LIVE: dict[str, tuple[float, dict]] = {}
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def month_chunks(start: str, end: str) -> list[tuple[str, str]]:
    """Split [start, end] (YYYY-MM-DD, inclusive) into calendar-month chunks."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out: list[tuple[str, str]] = []
    cur = s
    while cur <= e:
        month_end = (cur + pd.offsets.MonthEnd(0)).normalize()
        chunk_end = min(month_end, e)
        out.append((cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cur = chunk_end + pd.Timedelta(days=1)
    return out


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


@dataclass
class OpenMeteoClient:
    cache_dir: Path = field(default_factory=lambda: DATA_RAW / "openmeteo")
    min_interval_s: float = 0.25          # <= 4 requests/s, far below 600/min
    timeout_s: float = 60.0
    offline: bool = False                 # True -> only read cache, never call the network
    _last_call: float = 0.0

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._http = httpx.Client(timeout=self.timeout_s)

    # ---------- low level ----------
    def _cache_path(self, url: str, params: dict) -> Path:
        key = json.dumps({"url": url, "params": params}, sort_keys=True)
        h = hashlib.sha256(key.encode()).hexdigest()[:24]
        api = url.split("//")[1].split(".")[0]
        return self.cache_dir / api / f"{h}.json"

    @retry(retry=retry_if_exception(_retryable), wait=wait_exponential(multiplier=2, min=2, max=60),
           stop=stop_after_attempt(6), reraise=True)
    def _fetch(self, url: str, params: dict) -> dict:
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()
        r = self._http.get(url, params=params)
        if r.status_code == 400:
            raise ValueError(f"Open-Meteo 400: {r.text[:500]}")
        r.raise_for_status()
        return r.json()

    def get_live(self, url: str, params: dict) -> dict:
        """Forecast requests that must be fresh, but not on every call: reuse an answer for LIVE_TTL_S, and if
        Open-Meteo refuses (rate limit on a shared host IP) fall back to the last answer up to LIVE_STALE_S old."""
        key = json.dumps({"url": url, "params": params}, sort_keys=True)
        now = time.monotonic()
        hit = _LIVE.get(key)
        if hit and now - hit[0] < LIVE_TTL_S:
            return hit[1]
        try:
            data = self._fetch_live(url, params)
        except Exception as exc:  # noqa: BLE001
            if hit and now - hit[0] < LIVE_STALE_S:
                log.warning("Open-Meteo unavailable (%s); serving the answer from %d min ago", type(exc).__name__, (now - hit[0]) // 60)
                return hit[1]
            raise
        _LIVE[key] = (now, data)
        return data

    @retry(retry=retry_if_exception(_retryable), wait=wait_exponential(multiplier=2, min=2, max=10),
           stop=stop_after_attempt(3), reraise=True)
    def _fetch_live(self, url: str, params: dict) -> dict:
        return self._fetch.__wrapped__(self, url, params)

    def get_json(self, url: str, params: dict, use_cache: bool = True) -> dict:
        path = self._cache_path(url, params)
        if use_cache and path.exists():
            return json.loads(path.read_text())
        if self.offline:
            raise FileNotFoundError(f"offline mode and no cache for {url} {params}")
        data = self._fetch(url, params)
        if use_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        return data

    # ---------- parsing ----------
    @staticmethod
    def to_frame(payload: dict, rename: dict[str, str]) -> pd.DataFrame:
        hourly = payload["hourly"]
        idx = pd.to_datetime(hourly["time"], utc=True)
        data = {new: hourly.get(old) for old, new in rename.items() if old in hourly}
        missing = [old for old in rename if old not in hourly]
        if missing:
            log.warning("variables missing in response: %s", missing)
        df = pd.DataFrame(data, index=idx).astype("float64")
        df.index.name = "ts_utc"
        return df

    # ---------- public API ----------
    def fetch_archive(self, lat: float, lon: float, start: str, end: str,
                      variables: list[str], model: str | None = None) -> pd.DataFrame:
        """Actual (reanalysis) weather -> columns act_<short>."""
        frames = []
        hourly = ",".join(OPENMETEO_VARS[v] for v in variables)
        for s, e in month_chunks(start, end):
            params = {"latitude": lat, "longitude": lon, "start_date": s, "end_date": e,
                      "hourly": hourly, "wind_speed_unit": "ms", "timezone": "GMT"}
            if model:
                params["models"] = model
            payload = self.get_json(ARCHIVE_URL, params)
            frames.append(self.to_frame(payload, {OPENMETEO_VARS[v]: f"act_{v}" for v in variables}))
            log.info("archive %s..%s ok", s, e)
        return pd.concat(frames).sort_index().pipe(lambda d: d[~d.index.duplicated()])

    def fetch_previous_runs(self, lat: float, lon: float, start: str, end: str,
                            variables: list[str], days: tuple[int, ...] = (0, 1, 2),
                            model: str | None = None) -> pd.DataFrame:
        """Archived forecasts at fixed leads -> columns fx{d}_<short>.

        `<var>` is the latest run (previous_day0); `<var>_previous_dayN` was issued N*24 h
        before the valid time.
        """
        frames = []
        rename: dict[str, str] = {}
        names: list[str] = []
        for v in variables:
            base = OPENMETEO_VARS[v]
            for d in days:
                om = base if d == 0 else f"{base}_previous_day{d}"
                names.append(om)
                rename[om] = f"fx{d}_{v}"
        for s, e in month_chunks(start, end):
            params = {"latitude": lat, "longitude": lon, "start_date": s, "end_date": e,
                      "hourly": ",".join(names), "wind_speed_unit": "ms", "timezone": "GMT"}
            if model:
                params["models"] = model
            payload = self.get_json(PREVIOUS_RUNS_URL, params)
            frames.append(self.to_frame(payload, rename))
            log.info("previous-runs %s..%s ok", s, e)
        return pd.concat(frames).sort_index().pipe(lambda d: d[~d.index.duplicated()])

    def fetch_live_forecast(self, lat: float, lon: float, variables: list[str],
                            model: str | None = None, past_days: int = 3,
                            forecast_days: int = 3) -> pd.DataFrame:
        """Latest run for recent past + next days. Never cached (always fresh).

        In live mode every lead uses the latest run, so we copy it to fx0_/fx1_/fx2_.
        """
        params = {"latitude": lat, "longitude": lon, "hourly": ",".join(OPENMETEO_VARS[v] for v in variables),
                  "past_days": past_days, "forecast_days": forecast_days,
                  "wind_speed_unit": "ms", "timezone": "GMT"}
        if model:
            params["models"] = model
        payload = self.get_live(FORECAST_URL, params)
        base = self.to_frame(payload, {OPENMETEO_VARS[v]: v for v in variables})
        out = {}
        for p in ("fx0_", "fx1_", "fx2_"):
            for v in variables:
                out[f"{p}{v}"] = base[v]
        return pd.DataFrame(out, index=base.index)
