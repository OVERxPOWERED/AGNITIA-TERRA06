import numpy as np
import pandas as pd
import pytest

from terra.engines.alerts import prob_below
from terra.engines.dispatch import plan
from terra.engines.dsm import DsmProfile, deviation_charges
from terra.engines.hybrid import combine
from terra.models.downscale import downscale_wind


def test_dispatch_feasible_and_battery_helps(cfg):
    t = 24
    gen = np.r_[np.zeros(8), np.full(8, 60.0), np.zeros(8)]
    dem = np.full(t, 25.0)
    r = plan(gen, dem, cfg.battery, cfg.costs)
    s = r.schedule
    bal = s.gen_mw - s.curtail_mw - s.charge_mw + s.discharge_mw + s.backup_mw - s.demand_mw
    assert np.allclose(bal, 0, atol=1e-6)
    assert s.soc_mwh.min() >= cfg.battery.soc_min_frac * cfg.battery.energy_mwh - 1e-6
    bigger = plan(gen, dem, cfg.battery.model_copy(update={"energy_mwh": 200, "power_mw": 50}), cfg.costs)
    assert bigger.kpis["backup_mwh"] <= r.kpis["backup_mwh"] + 1e-6


def test_prob_below_monotone():
    q = np.array([[1, 2, 5, 8, 9.0]])
    p = [prob_below(q, x)[0] for x in (0.5, 2, 5, 8, 20)]
    assert p == sorted(p) and p[2] == pytest.approx(0.5)


def test_combine_bounds():
    qs = np.array([[0, 1, 5, 9, 10.0]])
    qw = np.array([[2, 3, 6, 9, 10.0]])
    out = combine(qs, qw, 40, 50, np.array([0.0]))
    assert (np.diff(out, axis=1) >= 0).all() and out.min() >= 0 and out.max() <= 90


def test_dsm_no_charge_within_tolerance():
    prof = DsmProfile(tolerance_pct={"wind": 10.0}, x_factor={"wind": 1.0},
                      slabs=[{"upto_pct": 1000, "inr_per_kwh": 1.0}], illustrative=True)
    ch = deviation_charges(np.array([20.0, 20.0]), np.array([24.0, 30.0]), 50.0, "wind", prof)
    assert ch["charge_inr"].iloc[0] == 0            # 8 % < 10 %
    assert ch["charge_inr"].iloc[1] == pytest.approx(10 / 100 * 50 * 0.25 * 1000)


def test_downscale_preserves_energy():
    idx = pd.date_range("2024-01-01 01:00", periods=24, freq="h", tz="UTC")
    hourly = pd.Series(np.linspace(5, 40, 24), index=idx)
    b = downscale_wind(hourly, 50)
    assert len(b) == 96
    assert abs(b.mean() - hourly.mean()) / hourly.mean() < 0.005
