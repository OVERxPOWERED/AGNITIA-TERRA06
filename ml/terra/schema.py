"""Column-name contract shared by every module (mirror of .agent/context/data-contracts.md)."""
from __future__ import annotations

# short name -> Open-Meteo hourly variable
OPENMETEO_VARS: dict[str, str] = {
    "ghi": "shortwave_radiation",
    "dni": "direct_normal_irradiance",
    "dhi": "diffuse_radiation",
    "cloud": "cloud_cover",
    "t2m": "temperature_2m",
    "rh2m": "relative_humidity_2m",
    "psfc": "surface_pressure",
    "ws10": "wind_speed_10m",
    "ws100": "wind_speed_100m",
    "wd100": "wind_direction_100m",
    "precip": "precipitation",
}
# Variables requested from the Previous Runs API (gusts not offered there).
FORECAST_VARS = list(OPENMETEO_VARS)
ACTUAL_VARS = list(OPENMETEO_VARS)

ACT = "act_"           # actual weather (never a model feature)
FX_LEADS = ("fx0_", "fx1_", "fx2_")   # previous_day0/1/2
FX = "fx_"             # lead-resolved forecast weather (after framing)
PHYS = "phys_"         # physics model output on forecast weather
HIST = "hist_"         # generation history observed at/before issue time
CAL = "cal_"           # calendar / solar geometry (deterministic)
ALLOWED_FEATURE_PREFIXES = (FX, PHYS, HIST, CAL)
EXTRA_FEATURES = ("lead_h",)

TARGETS = {"solar": "solar_mw", "wind": "wind_mw"}
QUANTILES = (0.05, 0.10, 0.50, 0.90, 0.95)
QCOLS = ("q05", "q10", "q50", "q90", "q95")
LEAD_BUCKETS = ((1, 12, "1-12", "fx0_"), (13, 36, "13-36", "fx1_"), (37, 48, "37-48", "fx2_"))


def lead_bucket(lead_h: int) -> str:
    for lo, hi, name, _ in LEAD_BUCKETS:
        if lo <= lead_h <= hi:
            return name
    raise ValueError(f"lead {lead_h} outside 1..48")


def lead_prefix(lead_h: int) -> str:
    for lo, hi, _, prefix in LEAD_BUCKETS:
        if lo <= lead_h <= hi:
            return prefix
    raise ValueError(f"lead {lead_h} outside 1..48")


def is_feature(col: str) -> bool:
    return col.startswith(ALLOWED_FEATURE_PREFIXES) or col in EXTRA_FEATURES
