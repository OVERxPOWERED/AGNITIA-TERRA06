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
    bad = {"solar_ac_mw": -1, "soc_min_frac": 0.95, "wind_turbines": "x", "nonsense": 1}
    clean, errors = validate(bad, cfg, "dewas", {"dewas"})
    assert "solar_ac_mw" in errors and "soc_min_frac" in errors and "wind_turbines" in errors and "nonsense" not in clean
    assert defaults(cfg, "dewas")["solar_ac_mw"] == cfg.solar.ac_capacity_mw


def test_factor_applies_availability_maintenance_and_condition():
    import pandas as pd

    cfg = load_config()
    t0 = pd.Timestamp("2026-05-01 00:00", tz="UTC")
    times = pd.date_range(t0 + pd.Timedelta(hours=1), periods=48, freq="h")
    win = [{"source": "wind", "start": "2026-05-01 10:30", "end": "2026-05-01 12:30", "units": 5}]   # IST = 05:00-07:00 UTC
    clean, err = validate({"turbines_out": 5, "maintenance": win, "soiling_loss_pct": 10, "soiling_rate_pct_per_day": 0},
                          cfg, "dewas", {"dewas"})
    assert not err
    a = apply_profile(cfg, get_location("dewas"), clean, {"wind": 1.1})
    fw = a.factor("wind", times, t0)
    assert abs(fw[0] - 0.8 * 1.1) < 1e-9                   # 5 of 25 turbines out, calibration 1.1
    assert abs(fw[5] - 0.6 * 1.1) < 1e-9                   # hour ending 06:00 UTC is inside the window
    assert abs(a.factor("solar", times, t0)[0] - 0.9) < 1e-9
    solar_only = apply_profile(cfg, get_location("dewas"), {"sources": "solar"})
    assert (solar_only.factor("wind", times, t0) == 0).all() and solar_only.summary["wind_mw"] == 0


def test_maintenance_window_validation():
    cfg = load_config()
    _, err = validate({"maintenance": [{"source": "wind", "start": "2026-05-02", "end": "2026-05-01", "units": 1}]},
                      cfg, "dewas", {"dewas"})
    assert "maintenance" in err


def test_measured_csv_parsing_and_hour_ending_resample():
    from terra.real.measured import UploadError, parse_csv

    rows = ["timestamp,solar_mw"] + [f"2026-05-01 {h:02d}:{m:02d},{h + m / 60:.3f}"
                                     for h in range(0, 3) for m in (0, 15, 30, 45)]
    hourly, notes = parse_csv("\n".join(rows), tz="UTC", stamp="start")
    assert notes["interval_min"] == 15
    # readings starting 00:00..00:45 cover the hour ending 01:00: mean of 0, .25, .5, .75
    first = hourly["solar_mw"].dropna().iloc[0]
    assert abs(first - 0.375) < 1e-9
    try:
        parse_csv("a,b\n1,2")
        raise AssertionError("expected UploadError")
    except UploadError:
        pass


def test_weather_disagreement_alert():
    import numpy as np
    import pandas as pd

    from terra.data.weather_models import disagreement_alerts

    t = pd.date_range("2026-05-01 01:00", periods=6, freq="h", tz="UTC")
    rows = []
    for m, v in (("a", [10, 10, 10, 10, 10, 10]), ("b", [11, 40, 45, 12, 10, 10])):
        rows.append(pd.DataFrame({"target_time_utc": t, "model": m, "hybrid_mw": np.array(v, float)}))
    al = disagreement_alerts(pd.concat(rows), 90.0, 0.25, t[0])
    assert len(al) == 1 and al[0].type == "WEATHER_DISAGREEMENT" and al[0].magnitude_mw == 35


def test_deviation_watch_flags_sustained_breach_only():
    import pandas as pd

    from terra.engines.deviation_watch import deviation_risk_alerts

    t0 = pd.Timestamp("2026-05-01 00:00", tz="UTC")
    idx = pd.date_range(t0 + pd.Timedelta(minutes=15), periods=24, freq="15min")
    committed = pd.Series(40.0, index=idx)
    expected = committed.copy()
    expected.iloc[4:10] = 52.0          # 6 blocks, 12 MW on 90 MW = 13% > 5% band
    expected.iloc[15:17] = 60.0         # 2 blocks only: too short to act on
    al = deviation_risk_alerts(expected, committed, 90.0, t0)
    assert len(al) == 1 and al[0].type == "DEVIATION_RISK" and al[0].severity == "critical"
    assert "Revise the schedule" in al[0].message and "13%" in al[0].message
