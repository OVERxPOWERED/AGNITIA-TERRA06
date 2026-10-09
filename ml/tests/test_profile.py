from terra.config import load_config
from terra.locations import get_location
from terra.profile import apply_profile, defaults, validate


def test_defaults_change_nothing():
    cfg = load_config()
    a = apply_profile(cfg, get_location("dewas"), {})
    assert a.summary["solar_scale"] == 1.0 and a.summary["wind_scale"] == 1.0
    assert a.user_cfg.capacity_mw("hybrid") == a.model_cfg.capacity_mw("hybrid")


def test_capacity_scaling_keeps_model_plant_unchanged():
    cfg = load_config()
    a = apply_profile(cfg, get_location("bhadla"), {"solar_ac_mw": 80, "wind_turbines": 50, "demand_peak_mw": 60})
    assert a.summary["solar_scale"] == 2.0 and a.summary["wind_scale"] == 2.0
    assert a.model_cfg.solar.ac_capacity_mw == cfg.solar.ac_capacity_mw          # models still see the trained plant
    assert a.user_cfg.demand.peak_mw == 60 and a.user_cfg.site.latitude == get_location("bhadla").latitude


def test_validation_flags_bad_values():
    cfg = load_config()
    clean, errors = validate({"solar_ac_mw": -1, "soc_min_frac": 0.95, "wind_turbines": "x", "nonsense": 1}, cfg, "dewas", {"dewas"})
    assert "solar_ac_mw" in errors and "soc_min_frac" in errors and "wind_turbines" in errors and "nonsense" not in clean
    assert defaults(cfg, "dewas")["solar_ac_mw"] == cfg.solar.ac_capacity_mw
