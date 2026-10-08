import numpy as np


def test_solar_zero_at_night_and_capped(cfg, ds):
    assert (ds.loc[ds["zenith"] >= 90, "twin_solar_mw"] == 0).all()
    assert ds["twin_solar_mw"].max() <= cfg.solar.ac_capacity_mw + 1e-9
    ist_hour = ds.index.tz_convert("Asia/Kolkata").hour
    peak_hour = ds["twin_solar_mw"].groupby(ist_hour).mean().idxmax()
    assert 11 <= peak_hour <= 14


def test_wind_power_curve_behaviour(cfg):
    from terra.data.wind_twin import turbine_power_frac
    ws = np.array([0.0, 2.0, 8.0, 15.0, 30.0])
    p = turbine_power_frac(ws, cfg.wind)
    assert p[0] == 0 and p[1] == 0 and 0 < p[2] < 1 and p[3] > 0.95 and p[4] == 0


def test_quality_checks_pass(cfg, ds):
    from terra.data.quality import check_dataset
    assert check_dataset(ds, cfg) == []
