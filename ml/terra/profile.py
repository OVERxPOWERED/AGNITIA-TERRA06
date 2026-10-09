"""Plant profile: what an operator tells the software about their plant (onboarding wizard and Settings).

One field table (`FIELDS`) drives the wizard, the Settings page, validation and the way values reach the pipeline,
so there is a single source of truth. Every field says what it *does*:
  forecast  - changes the forecast (capacity-scaled; the trained models assume the base plant's technology)
  plan      - changes battery, backup, demand or alert planning only
  display   - the name shown on every page
  recorded  - stored and shown, but the current models are trained for the base layout and ignore it
Values the operator never entered fall back to the base config and are labelled "assumed" in the UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from terra.config import TerraConfig
from terra.locations import Location, config_for

STEPS: list[dict] = [
    {"id": "plant", "title": "Your plant", "blurb": "Name it so every page can say whose numbers these are."},
    {"id": "site", "title": "Location", "blurb": "Where the plant stands. Weather for this spot drives every forecast."},
    {"id": "solar", "title": "Solar", "blurb": "The solar array. Capacity scales the solar forecast."},
    {"id": "wind", "title": "Wind", "blurb": "The wind farm. Turbines times rated power sets the wind capacity."},
    {"id": "storage", "title": "Battery and backup", "blurb": "Used by the dispatch plan: when to charge, discharge or call backup."},
    {"id": "demand", "title": "Demand", "blurb": "The supply the plant has to meet. Shortfalls and backup are measured against it."},
    {"id": "alerts", "title": "Alerts", "blurb": "When the forecast is too uncertain to rely on."},
]


@dataclass(frozen=True)
class Field:
    key: str
    step: str
    label: str
    kind: str                       # text | number | select
    effect: str                     # forecast | plan | recorded
    help: str
    unit: str = ""
    min: float | None = None
    max: float | None = None
    step_size: float | None = None
    path: tuple[str, ...] = ()      # where the default lives in TerraConfig
    verify: bool = False            # unverified rate: shown as illustrative
    required: bool = False


FIELDS: list[Field] = [
    Field("plant_name", "plant", "Plant name", "text", "display", "Shown in the bar under the header on every page.", required=True),
    Field("operator", "plant", "Operator", "text", "recorded", "Optional. The company or team running the plant."),
    Field("location_id", "site", "Site", "select", "forecast", "Pick from the allowed sites. Custom coordinates need a validated model for that region.", required=True),
    Field("solar_ac_mw", "solar", "Solar AC capacity", "number", "forecast", "Inverter output limit. The solar forecast scales with this.", "MW", 1, 500, 1, ("solar", "ac_capacity_mw")),
    Field("solar_dc_mw", "solar", "Solar DC capacity", "number", "recorded", "Panel nameplate capacity.", "MW", 1, 700, 1, ("solar", "dc_capacity_mw")),
    Field("tilt_deg", "solar", "Panel tilt", "number", "recorded", "Angle from horizontal.", "degrees", 0, 90, 1, ("solar", "tilt_deg")),
    Field("azimuth_deg", "solar", "Panel azimuth", "number", "recorded", "Compass direction the panels face; 180 is due south.", "degrees", 0, 359, 1, ("solar", "azimuth_deg")),
    Field("wind_turbines", "wind", "Number of turbines", "number", "forecast", "Wind capacity is turbines times rated power.", "", 1, 300, 1, ("wind", "n_turbines")),
    Field("wind_rated_mw", "wind", "Rated power per turbine", "number", "forecast", "Nameplate output of one turbine.", "MW", 0.5, 8, 0.1, ("wind", "rated_mw")),
    Field("hub_height_m", "wind", "Hub height", "number", "recorded", "Height of the rotor centre.", "m", 30, 180, 1, ("wind", "hub_height_m")),
    Field("battery_power_mw", "storage", "Battery power", "number", "plan", "Most the battery can charge or discharge at once.", "MW", 0, 500, 1, ("battery", "power_mw")),
    Field("battery_energy_mwh", "storage", "Battery energy", "number", "plan", "Total storage capacity.", "MWh", 0, 2000, 1, ("battery", "energy_mwh")),
    Field("round_trip_eff", "storage", "Round-trip efficiency", "number", "plan", "Share of energy you get back out. 0.90 means 90%.", "", 0.5, 1, 0.01, ("battery", "round_trip_eff")),
    Field("soc_min_frac", "storage", "Lowest charge level", "number", "plan", "Reserve the battery never goes below, as a fraction.", "", 0, 0.9, 0.01, ("battery", "soc_min_frac")),
    Field("soc_max_frac", "storage", "Highest charge level", "number", "plan", "Ceiling the battery never goes above, as a fraction.", "", 0.1, 1, 0.01, ("battery", "soc_max_frac")),
    Field("backup_inr_per_mwh", "storage", "Backup cost", "number", "plan", "Cost of covering a shortfall (gas, diesel or bought power).", "INR/MWh", 0, 100000, 100, ("costs", "backup_inr_per_mwh"), verify=True),
    Field("demand_peak_mw", "demand", "Peak demand to serve", "number", "plan", "The load profile scales to this peak.", "MW", 1, 1000, 1, ("demand", "peak_mw")),
    Field("low_trust_score", "alerts", "Low-confidence alert below", "number", "plan", "Raise an alert when an hour's trust score drops under this (0 to 100).", "score", 0, 100, 1, ("alerts", "low_trust_score")),
]
BY_KEY = {f.key: f for f in FIELDS}


def _get(cfg: TerraConfig, path: tuple[str, ...]):
    o = cfg
    for p in path:
        o = getattr(o, p)
    return o


def defaults(cfg: TerraConfig, home_id: str) -> dict:
    d = {"plant_name": "My plant", "operator": "", "location_id": home_id}
    d.update({f.key: _get(cfg, f.path) for f in FIELDS if f.path})
    return d


def schema(cfg: TerraConfig, home_id: str) -> dict:
    return {
        "steps": STEPS,
        "fields": [{"key": f.key, "step": f.step, "label": f.label, "kind": f.kind, "effect": f.effect, "help": f.help,
                    "unit": f.unit, "min": f.min, "max": f.max, "step_size": f.step_size, "verify": f.verify,
                    "required": f.required} for f in FIELDS],
        "defaults": defaults(cfg, home_id),
    }


def validate(values: dict, cfg: TerraConfig, home_id: str, valid_locations: set[str]) -> tuple[dict, dict[str, str]]:
    """Returns (clean values for the fields that were entered, errors by field key). Unknown keys are dropped."""
    clean: dict = {}
    errors: dict[str, str] = {}
    for k, v in values.items():
        f = BY_KEY.get(k)
        if f is None or v is None or v == "":
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
            clean[k] = int(x) if k == "wind_turbines" else x
        elif k == "location_id":
            if v not in valid_locations:
                errors[k] = "Choose one of the allowed sites."
                continue
            clean[k] = v
        else:
            clean[k] = str(v).strip()[:80]
    eff = {**defaults(cfg, home_id), **clean}
    if eff["soc_min_frac"] >= eff["soc_max_frac"]:
        errors["soc_min_frac"] = "The lowest charge level must be below the highest."
    if eff["solar_dc_mw"] < eff["solar_ac_mw"] * 0.8:
        errors["solar_dc_mw"] = "DC capacity is usually at least as large as AC capacity."
    if eff["battery_power_mw"] > 0 and eff["battery_energy_mwh"] <= 0:
        errors["battery_energy_mwh"] = "A battery with power needs some energy capacity."
    return clean, errors


@dataclass
class Applied:
    user_cfg: TerraConfig
    model_cfg: TerraConfig
    summary: dict = field(default_factory=dict)


def apply_profile(base: TerraConfig, loc: Location, clean: dict) -> Applied:
    """Build the config the plan uses (`user_cfg`) and the config the trained models were built for (`model_cfg`)."""
    model_cfg = config_for(base, loc)                 # base plant at the chosen site: what the models were trained for
    v = {**{f.key: _get(base, f.path) for f in FIELDS if f.path}, **clean}
    solar = model_cfg.solar.model_copy(update={"ac_capacity_mw": v["solar_ac_mw"], "dc_capacity_mw": v["solar_dc_mw"],
                                               "tilt_deg": v["tilt_deg"], "azimuth_deg": v["azimuth_deg"]})
    wind = model_cfg.wind.model_copy(update={"n_turbines": int(v["wind_turbines"]), "rated_mw": v["wind_rated_mw"],
                                             "hub_height_m": v["hub_height_m"]})
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
    summary = {
        "plant_name": name, "location": loc.name,
        "solar_ac_mw": user.solar.ac_capacity_mw, "wind_mw": user.wind.capacity_mw,
        "battery_mw": user.battery.power_mw, "battery_mwh": user.battery.energy_mwh, "demand_peak_mw": user.demand.peak_mw,
        "solar_scale": round(user.capacity_mw("solar") / model_cfg.capacity_mw("solar"), 4),
        "wind_scale": round(user.capacity_mw("wind") / model_cfg.capacity_mw("wind"), 4),
    }
    return Applied(user_cfg=user, model_cfg=model_cfg, summary=summary)
