from __future__ import annotations

from fastapi import APIRouter

from app.services import runs

router = APIRouter(tags=["docs"])


@router.get("/assumptions")
def assumptions() -> dict:
    return {"data_assumptions_md": runs.read_doc("data-assumptions.md"),
            "calibration_md": runs.read_doc("calibration.md"),
            "real_data_results_md": runs.read_doc("real-data-results.md")}


@router.get("/trust")
def trust_summary() -> dict:
    e = runs.evaluation()
    return {"solar": e.get("trust_solar"), "wind": e.get("trust_wind")}
