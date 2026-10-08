from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from terra.engines.dsm import schedule_csv

from app.schemas.api import DsmRow, DsmSummary
from app.services import runs

router = APIRouter(tags=["dsm"])


@router.get("/dsm/summary", response_model=DsmSummary)
def summary() -> DsmSummary:
    d = runs.evaluation()["dsm"]
    return DsmSummary(illustrative_rates=d["illustrative_rates"], chosen_level=d["chosen_level"],
                      rows=[DsmRow(**r) for r in d["table"]])


@router.get("/dsm/schedule.csv", response_class=PlainTextResponse)
def schedule(source: Literal["solar", "wind", "hybrid"] = "hybrid") -> str:
    s = runs.latest()["dsm_schedule"]
    if s is None:
        raise HTTPException(404, "no day-ahead schedule in the latest run")
    series = pd.Series(s[source].to_numpy(), index=pd.DatetimeIndex(s["block_end_utc"]))
    return schedule_csv(series)
