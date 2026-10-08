from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from app.schemas.api import DispatchPoint, DispatchResponse, Kpis
from app.services import runs

router = APIRouter(tags=["dispatch"])


@router.get("/dispatch", response_model=DispatchResponse)
def dispatch(strategy: Literal["advisor", "rule", "none"] = "advisor") -> DispatchResponse:
    r = runs.latest()
    d = r["dispatch"]
    d = d[d["strategy"] == strategy].copy()
    d["target_time_utc"] = d["target_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    pts = [DispatchPoint(**row) for row in d[list(DispatchPoint.model_fields)].to_dict(orient="records")]
    return DispatchResponse(strategy=strategy, points=pts, kpis={k: Kpis(**v) for k, v in r["dispatch_kpis"].items()})
