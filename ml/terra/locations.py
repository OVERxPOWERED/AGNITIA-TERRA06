"""Allowlisted sites for the /location feature (config/locations.yaml)."""
from __future__ import annotations

from dataclasses import dataclass

from terra.config import TerraConfig, load_yaml


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    region: str
    latitude: float
    longitude: float
    altitude_m: float
    note: str = ""


def load_locations() -> tuple[list[Location], str]:
    raw = load_yaml("locations.yaml")
    return [Location(**x) for x in raw["locations"]], raw.get("default", raw["locations"][0]["id"])


def get_location(loc_id: str) -> Location | None:
    return next((x for x in load_locations()[0] if x.id == loc_id), None)


def config_for(cfg: TerraConfig, loc: Location) -> TerraConfig:
    """The same plant placed at `loc`: only the site block changes."""
    site = cfg.site.model_copy(update={"name": f"{loc.name}, {loc.region} (same plant, live weather)",
                                       "latitude": loc.latitude, "longitude": loc.longitude, "altitude_m": loc.altitude_m})
    return cfg.model_copy(update={"site": site})
