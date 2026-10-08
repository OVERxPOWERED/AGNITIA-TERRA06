from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import ImpactResponse
from app.services import runs

router = APIRouter(tags=["impact"])


@router.get("/impact", response_model=ImpactResponse)
def impact() -> ImpactResponse:
    e = runs.evaluation()
    return ImpactResponse(impact=e["impact"], value_of_forecast=e["value_of_forecast"], hybrid=e["hybrid"],
                          sources=[e["impact"].get("emission_factor_source", ""),
                                   "Weather data by Open-Meteo.com (CC BY 4.0)"])
