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
import os
import threading
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

LIVE_TTL_S = 30 * 60            # live forecasts change a few times a day; one request per place per 30 minutes
PREFETCH_MAX_AGE_S = 2 * 3600   # a published prefetch copy is used while it is younger than this
LIVE_STALE_S = 6 * 3600         # how old a copy may be when Open-Meteo is refusing requests
_LIVE: dict[str, tuple[float, dict]] = {}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def payload_key(url: str, params: dict) -> str:
    """Stable name for one request (the prefetch workflow publishes <key>.json for each)."""
    return hashlib.sha256(json.dumps({"url": url, "params": params}, sort_keys=True).encode()).hexdigest()[:24]


def _lock_for(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


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

    def get_live(self, url: str, params: dict, force: bool = False) -> dict:
        """Live forecast request, spending as few Open-Meteo calls as possible. Order of preference:
        1. this process's memory (LIVE_TTL_S), 2. the disk copy (same TTL, survives restarts),
        3. the prefetched copy published by the scheduled workflow (PREFETCH_MAX_AGE_S), 4. a real request.
        If the real request is refused (free-tier limit, shared host address) any copy up to LIVE_STALE_S old is used.
        Concurrent callers for the same request share one fetch. `force` skips 1-3 (used by the prefetch job)."""
        key = payload_key(url, params)
        with _lock_for(key):
            now = time.time()
            if not force:
                for age, data in (self._mem(key), self._disk(key)):
                    if data is not None and age < LIVE_TTL_S:
                        return data
                pre = self._prefetched(key)
                if pre is not None and pre[0] < PREFETCH_MAX_AGE_S:
                    self._remember(key, pre[1], pre[2])
                    return pre[1]
            try:
                data = self._fetch_live(url, params)
            except Exception as exc:  # noqa: BLE001
                pre = self._prefetched(key)
                best = [x for x in (self._mem(key), self._disk(key), pre) if x and x[1] is not None]
                if best:
                    age, data = min(best, key=lambda x: x[0])[:2]
                    if age < LIVE_STALE_S:
                        log.warning("Open-Meteo unavailable (%s); serving a copy that is %d min old",
                                    type(exc).__name__, age // 60)
                        return data
                raise
            self._remember(key, data, now)
            return data

    # --- live-copy stores -------------------------------------------------------------------------------------
    def _mem(self, key: str) -> tuple[float, dict | None]:
        hit = _LIVE.get(key)
        return (time.time() - hit[0], hit[1]) if hit else (float("inf"), None)

    def _live_path(self, key: str) -> Path:
        return self.cache_dir / "live" / f"{key}.json"

    def _disk(self, key: str) -> tuple[float, dict | None]:
        p = self._live_path(key)
        try:
            d = json.loads(p.read_text())
            return time.time() - d["fetched_at"], d["payload"]
        except Exception:  # noqa: BLE001
            return float("inf"), None

    def _remember(self, key: str, data: dict, fetched_at: float) -> None:
        _LIVE[key] = (fetched_at, data)
        try:
            p = self._live_path(key)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"fetched_at": fetched_at, "payload": data}))
        except OSError:
            pass

    def _prefetched(self, key: str) -> tuple[float, dict, float] | None:
        """(age_s, payload, fetched_at) from the published prefetch folder, if configured and present."""
        base = os.environ.get("TERRA_WEATHER_PREFETCH_URL", "").strip().rstrip("/")
        if not base:
            return None
        try:
            r = self._http.get(f"{base}/{key}.json", timeout=10.0)
            if r.status_code != 200:
                return None
            d = r.json()
            return time.time() - d["fetched_at"], d["payload"], d["fetched_at"]
        except Exception:  # noqa: BLE001
            return None

    @retry(retry=retry_if_exception(_retryable), wait=wait_exponential(multiplier=2, min=2, max=10),
           stop=stop_after_attempt(3), reraise=True)
    def _fetch_live(self, url: str, params: dict) -> dict:
        key = os.environ.get("TERRA_OPENMETEO_API_KEY", "").strip()
        if key:        # paid plan: dedicated host and limits instead of the shared free tier
            url = url.replace("//api.open-meteo.com", "//customer-api.open-meteo.com")
            params = {**params, "apikey": key}
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

    @staticmethod
    def live_params(lat: float, lon: float, variables: list[str], model: str | None = None, past_days: int = 3,
                    forecast_days: int = 3) -> dict:
        params = {"latitude": lat, "longitude": lon, "hourly": ",".join(OPENMETEO_VARS[v] for v in variables),
                  "past_days": past_days, "forecast_days": forecast_days,
                  "wind_speed_unit": "ms", "timezone": "GMT"}
        if model:
            params["models"] = model
        return params

    def fetch_live_forecast(self, lat: float, lon: float, variables: list[str],
                            model: str | None = None, past_days: int = 3,
                            forecast_days: int = 3) -> pd.DataFrame:
        """Latest run for recent past + next days. Never cached (always fresh).

        In live mode every lead uses the latest run, so we copy it to fx0_/fx1_/fx2_.
        """
        params = self.live_params(lat, lon, variables, model, past_days, forecast_days)
        payload = self.get_live(FORECAST_URL, params)
        base = self.to_frame(payload, {OPENMETEO_VARS[v]: v for v in variables})
        out = {}
        for p in ("fx0_", "fx1_", "fx2_"):
            for v in variables:
                out[f"{p}{v}"] = base[v]
        return pd.DataFrame(out, index=base.index)
