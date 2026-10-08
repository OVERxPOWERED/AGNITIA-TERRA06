from __future__ import annotations

import math
from typing import Literal

from fastapi import APIRouter

from app.schemas.api import ModelRow, ModelsResponse
from app.services import runs

router = APIRouter(tags=["models"])


@router.get("/models/compare", response_model=ModelsResponse)
def compare(source: Literal["solar", "wind"] = "solar", split: Literal["val_cal", "test"] = "test",
            by: Literal["lead_bucket"] | None = None, daylight: bool = False) -> ModelsResponse:
    t = runs.compare_models(source, split, by, daylight=daylight)
    rows = [ModelRow(**{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()
                        if k in ModelRow.model_fields}) for r in t.to_dict(orient="records")]
    is_daylight_only = daylight and source == "solar"
    return ModelsResponse(source=source, split=split, rows=rows, daylight_only=is_daylight_only)
