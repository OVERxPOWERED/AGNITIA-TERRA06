# ruff: noqa: E501  (the field table reads best one field per line)
"""Plant profile: what an operator tells the software about their plant (onboarding wizard and Settings).

One field table (`FIELDS`) drives the wizard, the Settings page, validation and the way values reach the pipeline,
so there is a single source of truth. Every field says what it *does*:
  forecast  - changes the forecast (through the physics model, equipment availability or the export limit)
  plan      - changes battery, backup, demand or alert planning
  display   - the name shown on every page
  recorded  - stored and shown only (nothing in the physics depends on it)
Values the operator never entered fall back to the base config and are labelled "assumed" in the UI.

How the forecast uses the profile (see `run_forecast(..., model_cfg=..., adjust=...)`):
  1. The trained models run for the plant they were trained on (`model_cfg`: base plant, chosen site).
  2. The physics twin runs for both plants on the same forecast weather; the hourly ratio
     physics(operator plant) / physics(trained plant) transfers geometry, tracker, DC/AC size, turbine model,
     hub height and unit counts to the ML forecast.
  3. Hourly factors then apply equipment availability (units out, maintenance windows), soiling, panel
     degradation and the calibration factor fitted from uploaded measured history.
  4. The hybrid forecast is clipped at the grid export limit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from terra.config import TerraConfig
from terra.locations import Location, config_for

IST = "Asia/Kolkata"

STEPS: list[dict] = [
    {"id": "plant", "title": "Your plant", "blurb": "Name it and say what it generates from."},
    {"id": "site", "title": "Location", "blurb": "Where the plant stands. Weather for this spot drives every forecast."},
    {"id": "solar", "title": "Solar array", "blurb": "Size, orientation and tracking go through the physics model; inverters set available capacity."},
    {"id": "solar_condition", "title": "Panel condition", "blurb": "Age and dirt reduce output. Leave blank if you don't track them."},
    {"id": "wind", "title": "Wind farm", "blurb": "Turbine model and hub height go through the physics model; turbines out of service reduce capacity."},
    {"id": "grid", "title": "Grid and maintenance", "blurb": "Export limit clips what can be sent out; planned maintenance removes units for a window."},
    {"id": "storage", "title": "Battery and backup", "blurb": "Used by the dispatch plan: when to charge, discharge or call backup."},
    {"id": "demand", "title": "Demand", "blurb": "The supply the plant has to meet. Shortfalls and backup are measured against it."},
    {"id": "alerts", "title": "Alerts", "blurb": "When the forecast is too uncertain to rely on."},
]

SOURCES = [{"value": "hybrid", "label": "Solar and wind"}, {"value": "solar", "label": "Solar only"},
           {"value": "wind", "label": "Wind only"}]
TRACKING = [{"value": "fixed", "label": "Fixed tilt"}, {"value": "single_axis", "label": "Single-axis tracker (east-west)"}]


def _turbine_options() -> list[dict]:
    try:
        from windpowerlib import get_turbine_types
        df = get_turbine_types(print_out=False)
        df = df[df["has_power_curve"]]
        return [{"value": t, "label": f"{m} {t} ({_rated_from_type(t):g} MW)"}
                for m, t in zip(df["manufacturer"], df["turbine_type"]) if _rated_from_type(t)]
    except Exception:  # noqa: BLE001 - library list unavailable -> only the default turbine
        return []


def _rated_from_type(turbine_type: str) -> float | None:
    m = re.search(r"/(\d{3,5})", turbine_type)
    return round(int(m.group(1)) / 1000, 3) if m else None


@dataclass(frozen=True)
class Field:
    key: str
    step: str
    label: str
    kind: str                       # text | number | select | site | windows
    effect: str                     # forecast | plan | display | recorded
    help: str
    unit: str = ""
    min: float | None = None
    max: float | None = None
    step_size: float | None = None
    path: tuple[str, ...] = ()      # where the default lives in TerraConfig
    default: object = None          # default when there is no config path
    options: tuple = ()
    verify: bool = False            # unverified rate: shown as illustrative
    applies: str = ""               # "solar" | "wind": hidden when the plant does not have that source


FIELDS: list[Field] = [
    Field("plant_name", "plant", "Plant name", "text", "display", "Shown in the bar under the header on every page."),
    Field("operator", "plant", "Operator", "text", "recorded", "The company or team running the plant. Shown in reports; it does not change the forecast."),
    Field("sources", "plant", "Generation sources", "select", "forecast", "What the plant generates from. A source you don't have is forecast as zero.", default="hybrid", options=tuple(SOURCES)),
    Field("location_id", "site", "Site", "site", "forecast", "Pick from the allowed sites. Custom coordinates need a validated model for that region."),

    Field("solar_ac_mw", "solar", "Solar AC capacity", "number", "forecast", "Inverter output limit.", "MW", 1, 500, 1, ("solar", "ac_capacity_mw"), applies="solar"),
    Field("solar_dc_mw", "solar", "Solar DC capacity", "number", "forecast", "Panel nameplate capacity. A higher DC/AC ratio fills the inverters earlier in the day.", "MW", 1, 700, 1, ("solar", "dc_capacity_mw"), applies="solar"),
    Field("tracking", "solar", "Mounting", "select", "forecast", "Trackers follow the sun from east to west and change the daily shape.", path=("solar", "tracking"), options=tuple(TRACKING), applies="solar"),
    Field("tilt_deg", "solar", "Panel tilt", "number", "forecast", "Angle from horizontal (fixed mounting).", "degrees", 0, 90, 1, ("solar", "tilt_deg"), applies="solar"),
    Field("azimuth_deg", "solar", "Panel azimuth", "number", "forecast", "Compass direction the panels face; 180 is due south (fixed mounting).", "degrees", 0, 359, 1, ("solar", "azimuth_deg"), applies="solar"),
    Field("n_inverters", "solar", "Number of inverters", "number", "forecast", "Used with the next answer to work out available solar capacity.", "", 1, 2000, 1, default=20, applies="solar"),
    Field("inverters_out", "solar", "Inverters out of service now", "number", "forecast", "Removes that share of solar capacity until you change it.", "", 0, 2000, 1, default=0, applies="solar"),

    Field("panel_age_years", "solar_condition", "Panel age", "number", "forecast", "Years since commissioning.", "years", 0, 40, 0.5, default=0, applies="solar"),
    Field("degradation_pct_per_year", "solar_condition", "Degradation per year", "number", "forecast", "Typical crystalline panels lose about 0.5% a year.", "%", 0, 3, 0.05, default=0.5, applies="solar"),
    Field("soiling_loss_pct", "solar_condition", "Soiling loss now", "number", "forecast", "Output lost to dust today, for example from your last inspection. 0 right after cleaning.", "%", 0, 40, 0.5, default=0, applies="solar"),
    Field("soiling_rate_pct_per_day", "solar_condition", "Soiling build-up per day", "number", "forecast", "How fast dust accumulates without rain or cleaning.", "%/day", 0, 2, 0.05, default=0.2, applies="solar"),

    Field("turbine_model", "wind", "Turbine model", "select", "forecast", "Sets the power curve. The list comes from the open windpowerlib turbine library.", path=("wind", "turbine_type"), applies="wind"),
    Field("wind_turbines", "wind", "Number of turbines", "number", "forecast", "Installed turbines.", "", 1, 300, 1, ("wind", "n_turbines"), applies="wind"),
    Field("wind_rated_mw", "wind", "Rated power per turbine", "number", "forecast", "Nameplate output of one turbine. Filled from the turbine model if you leave it blank.", "MW", 0.5, 10, 0.05, ("wind", "rated_mw"), applies="wind"),
    Field("hub_height_m", "wind", "Hub height", "number", "forecast", "Height of the rotor centre. Higher hubs see stronger wind.", "m", 30, 180, 1, ("wind", "hub_height_m"), applies="wind"),
    Field("turbines_out", "wind", "Turbines out of service now", "number", "forecast", "Removes those turbines until you change it.", "", 0, 300, 1, default=0, applies="wind"),

    Field("export_limit_mw", "grid", "Grid export limit", "number", "forecast", "Most the connection can take. Forecast output above it is shown as curtailed. Leave blank for no limit.", "MW", 1, 2000, 1),
    Field("maintenance", "grid", "Planned maintenance", "windows", "forecast", "Units taken out for a period. Times are in IST."),

    Field("battery_power_mw", "storage", "Battery power", "number", "plan", "Most the battery can charge or discharge at once. 0 if there is no battery.", "MW", 0, 500, 1, ("battery", "power_mw")),
    Field("battery_energy_mwh", "storage", "Battery energy capacity", "number", "plan", "Total storage capacity. 0 if there is no battery.", "MWh", 0, 2000, 1, ("battery", "energy_mwh")),
    Field("round_trip_eff", "storage", "Round-trip efficiency", "number", "plan", "Share of energy you get back out. 0.90 means 90%.", "", 0.5, 1, 0.01, ("battery", "round_trip_eff")),
    Field("soc_min_frac", "storage", "Lowest charge level", "number", "plan", "Reserve the battery never goes below, as a fraction.", "", 0, 0.9, 0.01, ("battery", "soc_min_frac")),
    Field("soc_max_frac", "storage", "Highest charge level", "number", "plan", "Ceiling the battery never goes above, as a fraction.", "", 0.1, 1, 0.01, ("battery", "soc_max_frac")),
    Field("backup_inr_per_mwh", "storage", "Backup cost", "number", "plan", "Cost of covering a shortfall (gas, diesel or bought power).", "INR/MWh", 0, 100000, 100, ("costs", "backup_inr_per_mwh"), verify=True),

    Field("demand_peak_mw", "demand", "Peak demand to serve", "number", "plan", "The load profile scales to this peak.", "MW", 1, 1000, 1, ("demand", "peak_mw")),
    Field("low_trust_score", "alerts", "Low-confidence alert below", "number", "plan", "Raise an alert when an hour's trust score drops under this (0 to 100).", "score", 0, 100, 1, ("alerts", "low_trust_score")),
]
BY_KEY = {f.key: f for f in FIELDS}
NAME_ONLY = {"plant_name", "operator", "location_id"}


def _get(cfg: TerraConfig, path: tuple[str, ...]):
    o = cfg
    for p in path:
        o = getattr(o, p)
    return o


def defaults(cfg: TerraConfig, home_id: str) -> dict:
    d: dict = {"plant_name": "", "operator": "", "location_id": home_id, "export_limit_mw": "", "maintenance": []}
    for f in FIELDS:
        if f.path:
            d[f.key] = _get(cfg, f.path)
        elif f.default is not None:
            d[f.key] = f.default
    return d


def schema(cfg: TerraConfig, home_id: str) -> dict:
    turbines = _turbine_options()
    out = []
    for f in FIELDS:
        opts = list(f.options) if f.key != "turbine_model" else turbines
        out.append({"key": f.key, "step": f.step, "label": f.label, "kind": f.kind, "effect": f.effect, "help": f.help,
                    "unit": f.unit, "min": f.min, "max": f.max, "step_size": f.step_size, "verify": f.verify,
                    "options": opts, "applies": f.applies})
    return {"steps": STEPS, "fields": out, "defaults": defaults(cfg, home_id)}


def _parse_ist(v: str) -> pd.Timestamp:
    t = pd.Timestamp(v)
    return (t.tz_localize(IST) if t.tzinfo is None else t).tz_convert("UTC")


def _clean_windows(raw, eff: dict) -> tuple[list[dict], str | None]:
    if not isinstance(raw, list):
        return [], "Maintenance must be a list of windows."
    out = []
    for i, w in enumerate(raw[:50]):
        try:
            src = str(w["source"])
            start, end = _parse_ist(str(w["start"])), _parse_ist(str(w["end"]))
            units = int(float(w["units"]))
        except Exception:  # noqa: BLE001
            return [], f"Window {i + 1}: fill in source, start, end and units."
        if src not in ("solar", "wind"):
            return [], f"Window {i + 1}: source must be solar or wind."
        if end <= start:
            return [], f"Window {i + 1}: the end must be after the start."
        total = eff["n_inverters"] if src == "solar" else eff["wind_turbines"]
        if units < 1 or units > total:
            return [], f"Window {i + 1}: units must be between 1 and {int(total)}."
        out.append({"source": src, "start": str(w["start"]), "end": str(w["end"]), "units": units,
                    "note": str(w.get("note", ""))[:80]})
    return out, None


def validate(values: dict, cfg: TerraConfig, home_id: str, valid_locations: set[str]) -> tuple[dict, dict[str, str]]:
    """Returns (clean values for the fields that were entered, errors by field key). Unknown keys are dropped."""
    clean: dict = {}
    errors: dict[str, str] = {}
    turbine_ids = {o["value"] for o in _turbine_options()} | {cfg.wind.turbine_type}
    for k, v in values.items():
        f = BY_KEY.get(k)
        if f is None or v is None or v == "" or (k == "maintenance" and v == []):
            continue
        if f.kind == "number":
            try:
                x = float(v)
            except (TypeError, ValueError):
                errors[k] = "Enter a number."
                continue
            if x != x or (f.min is not None and x < f.min) or (f.max is not None and x > f.max):
                errors[k] = f"Enter a value between {f.min:g} and {f.max:g}{(' ' + f.unit) if f.unit else ''}."
                continue
            clean[k] = int(x) if k in ("wind_turbines", "n_inverters", "inverters_out", "turbines_out") else x
        elif f.kind == "site":
            if v not in valid_locations:
                errors[k] = "Choose one of the allowed sites."
                continue
            clean[k] = v
        elif f.kind == "select":
            allowed = turbine_ids if k == "turbine_model" else {o["value"] for o in f.options}
            if v not in allowed:
                errors[k] = "Choose one of the listed options."
                continue
            clean[k] = v
        elif f.kind == "windows":
            clean[k] = v                                  # checked below, once counts are known
        else:
            clean[k] = str(v).strip()[:80]
    eff = {**defaults(cfg, home_id), **clean}
    if "turbine_model" in clean and "wind_rated_mw" not in clean:
        eff["wind_rated_mw"] = _rated_from_type(clean["turbine_model"]) or eff["wind_rated_mw"]
    if eff["soc_min_frac"] >= eff["soc_max_frac"]:
        errors["soc_min_frac"] = "The lowest charge level must be below the highest."
    if eff["solar_dc_mw"] < eff["solar_ac_mw"] * 0.8:
        errors["solar_dc_mw"] = "DC capacity is usually at least as large as AC capacity."
    if eff["battery_power_mw"] > 0 and eff["battery_energy_mwh"] <= 0:
        errors["battery_energy_mwh"] = "A battery with power needs some energy capacity."
    if eff["inverters_out"] > eff["n_inverters"]:
        errors["inverters_out"] = "More inverters out than installed."
    if eff["turbines_out"] > eff["wind_turbines"]:
        errors["turbines_out"] = "More turbines out than installed."
    if "maintenance" in clean:
        wins, err = _clean_windows(clean["maintenance"], eff)
        if err:
            errors["maintenance"] = err
            clean.pop("maintenance")
        else:
            clean["maintenance"] = wins
    return clean, errors


@dataclass
class Applied:
    """Everything the pipeline needs to turn the trained plant's forecast into the operator's."""
    user_cfg: TerraConfig
    model_cfg: TerraConfig
    sources: set[str]
    values: dict
    calibration: dict[str, float] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)

    @property
    def export_limit_mw(self) -> float | None:
        v = self.values.get("export_limit_mw")
        return float(v) if v not in (None, "") else None

    def factor(self, source: str, target_times: pd.DatetimeIndex, issue_time: pd.Timestamp) -> np.ndarray:
        """Hourly multiplier on top of the physics ratio: availability x condition x calibration."""
        n = len(target_times)
        if source not in self.sources:
            return np.zeros(n)
        v = self.values
        units = v["n_inverters"] if source == "solar" else v["wind_turbines"]
        out_now = v["inverters_out"] if source == "solar" else v["turbines_out"]
        units_out = np.full(n, float(out_now))
        tt = pd.DatetimeIndex(target_times)
        for w in v.get("maintenance", []):
            if w["source"] != source:
                continue
            s, e = _parse_ist(w["start"]), _parse_ist(w["end"])
            # an hour-ending point at t covers (t-1h, t]; it is affected if that hour overlaps the window
            hit = (tt > s) & (tt - pd.Timedelta(hours=1) < e)
            units_out[hit] += w["units"]
        avail = np.clip(1 - units_out / max(units, 1), 0, 1)
        f = avail
        if source == "solar":
            degr = 1 - min(v["panel_age_years"] * v["degradation_pct_per_year"] / 100, 0.5)
            days = (tt - issue_time).total_seconds().to_numpy() / 86400
            soil = np.clip(v["soiling_loss_pct"] + v["soiling_rate_pct_per_day"] * days, 0, 40) / 100
            f = f * degr * (1 - soil)
        return f * self.calibration.get(source, 1.0)


def apply_profile(base: TerraConfig, loc: Location, clean: dict, calibration: dict[str, float] | None = None) -> Applied:
    """Build the operator's plant (`user_cfg`) and the plant the models were trained for (`model_cfg`)."""
    model_cfg = config_for(base, loc)                 # base plant at the chosen site: what the models were trained for
    v = {**defaults(base, loc.id), **clean}
    if "turbine_model" in clean and "wind_rated_mw" not in clean:
        v["wind_rated_mw"] = _rated_from_type(clean["turbine_model"]) or v["wind_rated_mw"]
    solar = model_cfg.solar.model_copy(update={"ac_capacity_mw": v["solar_ac_mw"], "dc_capacity_mw": v["solar_dc_mw"],
                                               "tilt_deg": v["tilt_deg"], "azimuth_deg": v["azimuth_deg"],
                                               "tracking": v["tracking"]})
    wind = model_cfg.wind.model_copy(update={"n_turbines": int(v["wind_turbines"]), "rated_mw": v["wind_rated_mw"],
                                             "hub_height_m": v["hub_height_m"], "turbine_type": v["turbine_model"]})
    battery = model_cfg.battery.model_copy(update={"power_mw": v["battery_power_mw"], "energy_mwh": v["battery_energy_mwh"],
                                                   "round_trip_eff": v["round_trip_eff"], "soc_min_frac": v["soc_min_frac"],
                                                   "soc_max_frac": v["soc_max_frac"]})
    demand = model_cfg.demand.model_copy(update={"peak_mw": v["demand_peak_mw"]})
    costs = model_cfg.costs.model_copy(update={"backup_inr_per_mwh": v["backup_inr_per_mwh"]})
    alerts = model_cfg.alerts.model_copy(update={"low_trust_score": v["low_trust_score"]})
    name = clean.get("plant_name") or f"{loc.name}, {loc.region}"
    site = model_cfg.site.model_copy(update={"name": name})
    user = model_cfg.model_copy(update={"solar": solar, "wind": wind, "battery": battery, "demand": demand,
                                        "costs": costs, "alerts": alerts, "site": site})
    sources = {"hybrid": {"solar", "wind"}, "solar": {"solar"}, "wind": {"wind"}}[v["sources"]]
    cal = {k: float(np.clip(x, 0.3, 1.6)) for k, x in (calibration or {}).items() if k in ("solar", "wind")}
    a = Applied(user_cfg=user, model_cfg=model_cfg, sources=sources, values=v, calibration=cal)
    solar_mw = user.solar.ac_capacity_mw if "solar" in sources else 0.0
    wind_mw = user.wind.capacity_mw if "wind" in sources else 0.0
    a.summary = {
        "plant_name": name, "location": loc.name, "sources": v["sources"],
        "solar_ac_mw": solar_mw, "wind_mw": round(wind_mw, 3),
        "battery_mw": user.battery.power_mw, "battery_mwh": user.battery.energy_mwh, "demand_peak_mw": user.demand.peak_mw,
        "solar_scale": round(solar_mw / model_cfg.capacity_mw("solar"), 4),
        "wind_scale": round(wind_mw / model_cfg.capacity_mw("wind"), 4),
        "export_limit_mw": a.export_limit_mw, "calibration": cal,
        "derate_now": {s: round(float(a.factor(s, pd.DatetimeIndex([pd.Timestamp.now(tz="UTC").floor("h")]),
                                                  pd.Timestamp.now(tz="UTC").floor("h"))[0]
                                         / max(cal.get(s, 1.0), 1e-9)), 4) for s in ("solar", "wind")},
    }
    return a

