from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from terra.config import load_config

from app.schemas.api import ForecastPoint, ForecastResponse, HistoryPoint, HistoryResponse
from app.services import runs

router = APIRouter(tags=["forecast"])


def _iso(s):
    return s.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/forecast", response_model=ForecastResponse)
def forecast(source: Literal["solar", "wind", "hybrid"] = "hybrid",
             horizon: int = Query(48, ge=1, le=48)) -> ForecastResponse:
    r = runs.latest()
    f = r["forecast"]
    f = f[(f["source"] == source) & (f["lead_h"] <= horizon)].sort_values("lead_h").copy()
    f["target_time_utc"] = _iso(f["target_time_utc"])
    cols = ["target_time_utc", "lead_h", "q05", "q10", "q50", "q90", "q95", "trust_score", "trust_level", "trust_reason"]
    pts = [ForecastPoint(**row) for row in f[cols].to_dict(orient="records")]
    return ForecastResponse(source=source, issue_time_utc=r["meta"]["issue_time_utc"], mode=r["meta"]["mode"],
                            capacity_mw=load_config().capacity_mw(source), points=pts)


@router.get("/forecast/history", response_model=HistoryResponse)
def history(source: Literal["solar", "wind"] = "solar", model: str = "ensemble",
            start: str | None = None, end: str | None = None, lead_h_max: int = Query(24, ge=1, le=48)
            ) -> HistoryResponse:
    """Actual vs predicted on the held-out test period (day-ahead issues at 00 UTC)."""
    p = runs.backtest(source)
    p = p[(p["model"] == model) & (p["split"] == "test") & (p["issue_time_utc"].dt.hour == 0)
          & (p["lead_h"] <= lead_h_max)].sort_values("target_time_utc")
    if start:
        p = p[p["target_time_utc"] >= start]
    if end:
        p = p[p["target_time_utc"] <= end]
    if not start and not end:
        p = p.head(24 * 14)
    p = p.assign(target_time_utc=_iso(p["target_time_utc"]), actual_mw=p["y"])
    pts = [HistoryPoint(**r) for r in p[["target_time_utc", "actual_mw", "q10", "q50", "q90"]].to_dict(orient="records")]
    return HistoryResponse(source=source, model=model, lead_h_max=lead_h_max, points=pts)
