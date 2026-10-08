"""Typed configuration loaded from config/site.yaml (and config/dsm.yaml).

Usage:
    from terra.config import load_config
    cfg = load_config()            # default path config/site.yaml
    cfg.solar.ac_capacity_mw
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from terra.paths import CONFIG_DIR


class SiteCfg(BaseModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_m: float = 0.0
    timezone: str = "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def _tz_valid(cls, v: str) -> str:
        pd.Timestamp("2025-01-01", tz=v)  # raises if unknown
        return v


class SolarCfg(BaseModel):
    dc_capacity_mw: float = Field(gt=0)
    ac_capacity_mw: float = Field(gt=0)
    tilt_deg: float = Field(ge=0, le=90)
    azimuth_deg: float = Field(ge=0, lt=360)
    albedo: float = Field(default=0.2, ge=0, le=1)
    gamma_pdc: float = Field(default=-0.0037, lt=0)
    system_loss_frac: float = Field(default=0.14, ge=0, lt=1)
    eta_inv_nom: float = Field(default=0.96, gt=0, le=1)


class WindCfg(BaseModel):
    turbine_type: str
    n_turbines: int = Field(gt=0)
    rated_mw: float = Field(gt=0)
    hub_height_m: float = Field(gt=10)
    wake_loss_frac: float = Field(default=0.07, ge=0, lt=1)
    electrical_loss_frac: float = Field(default=0.02, ge=0, lt=1)
    cut_out_ms: float = 25.0

    @property
    def capacity_mw(self) -> float:
        return self.n_turbines * self.rated_mw


class BatteryCfg(BaseModel):
    power_mw: float = Field(ge=0)
    energy_mwh: float = Field(ge=0)
    round_trip_eff: float = Field(default=0.9, gt=0, le=1)
    soc_min_frac: float = Field(default=0.1, ge=0, le=1)
    soc_max_frac: float = Field(default=0.9, ge=0, le=1)
    soc_init_frac: float = Field(default=0.5, ge=0, le=1)
    degradation_inr_per_mwh: float = 300.0
    reserve_factor: float = 1.0

    @model_validator(mode="after")
    def _soc_order(self) -> "BatteryCfg":
        if not self.soc_min_frac <= self.soc_init_frac <= self.soc_max_frac:
            raise ValueError("require soc_min_frac <= soc_init_frac <= soc_max_frac")
        return self


class DemandCfg(BaseModel):
    peak_mw: float = Field(gt=0)
    temp_coeff_per_c: float = 0.01
    noise_std_frac: float = 0.02
    shape_source: Literal["parametric", "india_hourly"] = "parametric"


class SolarRealismCfg(BaseModel):
    ar1_phi: float = 0.7
    ar1_sigma: float = 0.06
    soiling_rate_per_day: float = 0.002
    soiling_reset_rain_mm: float = 5.0
    outage_rate_per_day: float = 0.02
    outage_mean_hours: float = 6.0
    outage_capacity_frac: float = 0.10


class WindRealismCfg(BaseModel):
    ar1_phi: float = 0.6
    ar1_sigma: float = 0.08
    outage_rate_per_day: float = 0.03
    outage_mean_hours: float = 12.0
    outage_capacity_frac: float = 0.12
    curtail_rate_per_day: float = 0.02
    curtail_mean_hours: float = 4.0
    curtail_level_frac: float = 0.6


class RealismCfg(BaseModel):
    seed: int = 42
    solar: SolarRealismCfg = SolarRealismCfg()
    wind: WindRealismCfg = WindRealismCfg()


class CostsCfg(BaseModel):
    backup_inr_per_mwh: float
    curtail_penalty_inr_per_mwh: float
    emission_factor_t_per_mwh: float
    emission_factor_source: str = ""


class AlertsCfg(BaseModel):
    low_quantile: float | dict[str, float] = 0.10
    high_quantile: float = 0.90
    ramp_quantile: float = 0.95
    quantile_basis: str = "train"
    low_generation_frac: float = 0.10
    high_generation_frac: float = 0.85
    ramp_mw_per_h: float = 20.0
    low_trust_score: float = 40
    min_probability: float = 0.6

    def get_low_quantile(self, source: str) -> float:
        if isinstance(self.low_quantile, dict):
            return float(self.low_quantile.get(source, 0.10))
        return float(self.low_quantile)


class WeatherCfg(BaseModel):
    forecast_model: Optional[str] = "ecmwf_ifs025"
    actual_model: Optional[str] = None
    start_date: str
    end_date: str


class SplitsCfg(BaseModel):
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str

    def bounds(self) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
        """UTC [start, end] (inclusive end-of-day) for each split."""
        def ts(d: str, end: bool) -> pd.Timestamp:
            t = pd.Timestamp(d, tz="UTC")
            return t + pd.Timedelta(hours=23) if end else t
        return {
            "train": (ts(self.train_start, False), ts(self.train_end, True)),
            "val": (ts(self.val_start, False), ts(self.val_end, True)),
            "test": (ts(self.test_start, False), ts(self.test_end, True)),
        }

    @model_validator(mode="after")
    def _ordered(self) -> "SplitsCfg":
        b = self.bounds()
        if not (b["train"][1] < b["val"][0] - pd.Timedelta(hours=47)
                and b["val"][1] < b["test"][0] - pd.Timedelta(hours=47)):
            raise ValueError("splits must be chronological with >= 48 h gaps")
        return self


class ForecastCfg(BaseModel):
    horizon_h: int = 48
    quantiles: list[float] = [0.05, 0.10, 0.50, 0.90, 0.95]
    train_issue_hours_utc: list[int] = [0, 6, 12, 18]
    dayahead_issue_hour_utc: int = 0


class TerraConfig(BaseModel):
    site: SiteCfg
    solar: SolarCfg
    wind: WindCfg
    battery: BatteryCfg
    demand: DemandCfg
    realism: RealismCfg = RealismCfg()
    costs: CostsCfg
    alerts: AlertsCfg = AlertsCfg()
    weather: WeatherCfg
    splits: SplitsCfg
    forecast: ForecastCfg = ForecastCfg()

    def capacity_mw(self, source: str) -> float:
        if source == "solar":
            return self.solar.ac_capacity_mw
        if source == "wind":
            return self.wind.capacity_mw
        if source == "hybrid":
            return self.solar.ac_capacity_mw + self.wind.capacity_mw
        raise ValueError(f"unknown source {source!r}")

    def hash(self) -> str:
        """Stable short hash, stored in every artifact's meta.json."""
        blob = json.dumps(self.model_dump(), sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


def load_config(path: str | Path | None = None) -> TerraConfig:
    path = Path(path) if path else CONFIG_DIR / "site.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return TerraConfig.model_validate(raw)


@lru_cache(maxsize=1)
def default_config() -> TerraConfig:
    return load_config()


def load_yaml(name: str) -> dict:
    """Load any other YAML from config/ (e.g. 'dsm.yaml', 'calibration/solar.yaml')."""
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
