from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from terra.engines.whatif import Scenario

from app.schemas.api import Kpis, WhatIfRequest, WhatIfResponse, WhatIfSide
from app.services.whatif import whatif as run

router = APIRouter(tags=["whatif"])


@router.post("/whatif", response_model=WhatIfResponse)
def whatif(req: WhatIfRequest) -> WhatIfResponse:
    try:
        sc = Scenario(**req.model_dump())
    except ValidationError as e:
        raise HTTPException(422, str(e)) from e
    res = run(sc)

    def side(x: dict) -> WhatIfSide:
        h = x["hybrid"].copy()
        h["target_time_utc"] = h["target_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return WhatIfSide(energy_mwh_p50=x["energy_mwh_p50"], kpis=Kpis(**x["kpis"]),
                          points=h[["target_time_utc", "q10", "q50", "q90"]].round(3).to_dict(orient="records"))

    return WhatIfResponse(before=side(res["before"]), after=side(res["after"]))
