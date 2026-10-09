"""Response/request models. The frontend's TypeScript types are generated from these (make types)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

Source = Literal["solar", "wind", "hybrid"]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorBody


class Health(BaseModel):
    status: str
    version: str
    mode: str
    latest_run: str | None = None
    latest_issue_time_utc: str | None = None


class SiteInfo(BaseModel):
    name: str
    latitude: float
    longitude: float
    timezone: str
    solar_ac_mw: float
    wind_mw: float
    battery_mw: float
    battery_mwh: float
    attribution: str
    plant_note: str


class ForecastPoint(BaseModel):
    target_time_utc: str
    lead_h: int
    q05: float
    q10: float
    q50: float
    q90: float
    q95: float
    trust_score: float
    trust_level: str
    trust_reason: str


class ForecastResponse(BaseModel):
    source: Source
    issue_time_utc: str
    mode: str
    capacity_mw: float
    points: list[ForecastPoint]


class HistoryPoint(BaseModel):
    target_time_utc: str
    actual_mw: float
    q10: float
    q50: float
    q90: float


class HistoryResponse(BaseModel):
    source: Literal["solar", "wind"]
    model: str
    lead_h_max: int
    points: list[HistoryPoint]


class ModelRow(BaseModel):
    model: str
    mae: float
    rmse: float
    nmae_pct: float
    nrmse_pct: float
    bias: float
    picp80: float
    picp90: float
    mpiw80_pct: float
    skill_vs_persistence: float | None = None
    lead_bucket: str | None = None


class ModelsResponse(BaseModel):
    source: Literal["solar", "wind"]
    split: str
    rows: list[ModelRow]
    daylight_only: bool = False


class AlertOut(BaseModel):
    id: str
    type: str
    source: str
    start_utc: str
    end_utc: str
    severity: Literal["info", "warning", "critical"]
    probability: float
    magnitude_mw: float
    message: str
    issue_time_utc: str
    acknowledged: bool = False


class DispatchPoint(BaseModel):
    target_time_utc: str
    gen_mw: float
    demand_mw: float
    charge_mw: float
    discharge_mw: float
    soc_mwh: float
    backup_mw: float
    curtail_mw: float


class Kpis(BaseModel):
    backup_mwh: float
    curtail_mwh: float
    cost_inr: float
    co2_t: float
    battery_throughput_mwh: float


class DispatchResponse(BaseModel):
    strategy: Literal["advisor", "rule", "none"]
    points: list[DispatchPoint]
    kpis: dict[str, Kpis]


class WhatIfRequest(BaseModel):
    irradiance_scale: float = 1.0
    wind_scale: float = 1.0
    solar_ac_mw: float | None = None
    wind_turbines: int | None = None
    battery_mw: float | None = None
    battery_mwh: float | None = None


class WhatIfSide(BaseModel):
    energy_mwh_p50: float
    kpis: Kpis
    points: list[dict]


class WhatIfResponse(BaseModel):
    before: WhatIfSide
    after: WhatIfSide


class DsmRow(BaseModel):
    source: str
    strategy: str
    charge_inr: float
    blocks_outside_tolerance_pct: float


class DsmSummary(BaseModel):
    illustrative_rates: bool
    chosen_level: dict[str, float]
    rows: list[DsmRow]


class ImpactResponse(BaseModel):
    impact: dict
    value_of_forecast: list[dict]
    hybrid: dict
    sources: list[str]


# ---- /locations: the same plant, placed at another allowlisted site, on live weather ----
class LocationInfo(BaseModel):
    id: str
    name: str
    region: str
    latitude: float
    longitude: float
    altitude_m: float
    note: str
    is_home: bool


class LocationJob(BaseModel):
    job_id: str
    location_id: str
    status: Literal["queued", "running", "done", "failed"]
    step: Literal["queued", "weather", "models", "plan", "second", "done"]
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    reused: bool = False


class PlantSummary(BaseModel):
    plant_name: str
    location: str
    solar_ac_mw: float
    wind_mw: float
    battery_mw: float
    battery_mwh: float
    demand_peak_mw: float
    solar_scale: float
    wind_scale: float
    entered: list[str]
    customised: bool
    sources: str = "hybrid"
    export_limit_mw: float | None = None
    calibration: dict[str, float] = {}
    derate_now: dict[str, float] = {}


class ProfileBody(BaseModel):
    values: dict[str, Any] = {}
    calibration: dict[str, float] = {}
    keys: dict[str, str] = {}               # optional provider keys (solcast, tomorrow); used for this run only


class WeatherModelPoint(BaseModel):
    target_time_utc: str
    solar_mw: float | None
    wind_mw: float | None
    hybrid_mw: float | None
    ghi: float | None
    ws100: float | None


class WeatherModelSeries(BaseModel):
    id: str
    label: str
    status: str
    points: list[WeatherModelPoint]


class ProfileCheck(BaseModel):
    clean: dict[str, Any]
    errors: dict[str, str]
    summary: PlantSummary | None = None


class BlockPoint(BaseModel):
    block_end_utc: str
    solar: float
    wind: float
    hybrid: float


class LocationResult(BaseModel):
    location: LocationInfo
    issue_time_utc: str
    generated_at: str
    solar: list[ForecastPoint]
    wind: list[ForecastPoint]
    hybrid: list[ForecastPoint]
    dispatch: list[DispatchPoint]
    kpis: Kpis
    dispatch_by_strategy: dict[str, list[DispatchPoint]]
    kpis_by_strategy: dict[str, Kpis]
    alerts: list[AlertOut]
    validated_here: bool
    caveat: str
    attribution: str
    plant: PlantSummary
    second_opinions: list[WeatherModelSeries] = []
    export_curtailed_mw: list[float] = []
    export_curtailed_mwh: float = 0.0
    dsm_schedule: list[BlockPoint] = []
    expected_blocks: list[BlockPoint] = []


# ---- accounts ----
class AuthIn(BaseModel):
    email: str
    password: str
    name: str = ""


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: str


class AuthOut(BaseModel):
    token: str
    user: UserOut


class PlantStored(BaseModel):
    site_id: str | None = None
    live_home: bool = False
    values: dict[str, Any] = {}
    calibration: dict[str, Any] = {}
    version: int = 0
    updated_at: str | None = None


class PlantIn(BaseModel):
    values: dict[str, Any] | None = None
    site_id: str | None = None
    live_home: bool | None = None
    calibration: dict[str, Any] | None = None


class CalibrationIn(BaseModel):
    csv: str
    timezone: str = "Asia/Kolkata"
    stamp: Literal["start", "end"] = "start"
    unit: Literal["MW", "kW"] = "MW"
    values: dict[str, Any] = {}
    location_id: str | None = None


class SchedulePut(BaseModel):
    date: str                                    # IST date YYYY-MM-DD
    blocks: list[list[Any]]                      # [[block_end_utc, mw], ...]
    source: Literal["hybrid"] = "hybrid"
