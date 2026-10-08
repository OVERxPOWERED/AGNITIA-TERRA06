import numpy as np
import pandas as pd
import pytest

from terra.engines.alerts import alert_skill, alert_thresholds, generate_alerts, prob_below
from terra.engines.dispatch import plan
from terra.engines.dsm import DsmProfile, deviation_charges
from terra.engines.hybrid import combine
from terra.engines.trust import hybrid_trust_score
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


def test_alert_thresholds_train_only_no_leakage(cfg, ds):
    th_orig = alert_thresholds(ds, cfg)
    corrupted = ds.copy()
    val_b = cfg.splits.bounds()["val"]
    test_b = cfg.splits.bounds()["test"]
    corrupted.loc[val_b[0]:val_b[1], ["solar_mw", "wind_mw"]] = 999999.0
    corrupted.loc[test_b[0]:test_b[1], ["solar_mw", "wind_mw"]] = -999999.0
    th_corrupted = alert_thresholds(corrupted, cfg)
    assert th_orig == th_corrupted


def test_alert_thresholds_mapping_and_scalar(cfg, ds):
    th_map = alert_thresholds(ds, cfg)
    th_scalar = alert_thresholds(ds, cfg, low_quantile=0.10)

    # Solar and hybrid use 0.10 in both, so low_mw matches
    assert th_map["solar"]["low_mw"] == th_scalar["solar"]["low_mw"]
    assert th_map["hybrid"]["low_mw"] == th_scalar["hybrid"]["low_mw"]
    # Wind uses P25 in mapping vs P10 in scalar -> wind low threshold is higher
    assert th_map["wind"]["low_mw"] > th_scalar["wind"]["low_mw"]

    # Custom mapping argument
    custom_map = {"solar": 0.15, "wind": 0.30, "hybrid": 0.20}
    th_custom = alert_thresholds(ds, cfg, low_quantile=custom_map)
    assert th_custom["wind"]["low_mw"] > th_map["wind"]["low_mw"]
    assert th_custom["solar"]["low_mw"] > th_map["solar"]["low_mw"]


def test_every_alert_type_can_fire_on_crafted_forecast(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=4, freq="h", tz="UTC")
    # Row 0: low generation, Row 1: ramp up, Row 2: high generation, Row 3: normal
    q_data = [
        [0.1, 0.2, 0.5, 0.8, 1.0],     # well below 3.0 MW -> LOW_GENERATION
        [5.0, 10.0, 20.0, 25.0, 30.0],  # jump from 0.5 to 20.0 (ramp 19.5 >= 10.0) -> RAMP
        [32.0, 35.0, 36.0, 38.0, 39.0], # well above 28.0 MW -> HIGH_GENERATION
        [10.0, 12.0, 15.0, 18.0, 20.0],
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    fc["cal_is_day"] = 1
    thrs = {"low_mw": 3.0, "high_mw": 28.0, "ramp_mw_per_h": 10.0}
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], thresholds=thrs)
    types = {a.type for a in alerts}
    assert "LOW_GENERATION" in types
    assert "HIGH_GENERATION" in types
    assert "RAMP" in types


def test_alert_message_contains_numeric_threshold(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=3, freq="h", tz="UTC")
    q_data = [
        [0.1, 0.2, 0.4, 0.6, 0.8],     # P(X < 3.2 MW) ~ 1.0 -> LOW
        [35.0, 36.0, 37.0, 38.0, 39.0], # ramp from 0.4 to 37.0 >= 8.5 MW/h -> RAMP + HIGH
        [35.0, 36.0, 37.0, 38.0, 39.0], # stays high > 30.0 MW -> HIGH
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    fc["cal_is_day"] = 1
    thrs = {"low_mw": 3.2, "high_mw": 30.0, "ramp_mw_per_h": 8.5}
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], thresholds=thrs)
    for a in alerts:
        if a.type == "LOW_GENERATION":
            assert "3.2 MW" in a.message
            assert "%" in a.message
        elif a.type == "HIGH_GENERATION":
            assert "30.0 MW" in a.message
            assert "%" in a.message
        elif a.type == "RAMP":
            assert "8.5 MW" in a.message


def test_generate_alerts_fallback_when_thresholds_missing(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=2, freq="h", tz="UTC")
    q_data = [
        [0.1, 0.2, 0.5, 0.8, 1.0],      # below 4.0 MW (10% of 40)
        [36.0, 37.0, 38.0, 39.0, 40.0],  # above 34.0 MW (85% of 40) & ramp 37.5 >= 20.0
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    fc["cal_is_day"] = 1
    # Calling with thresholds=None should fall back to config fraction/MW
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], thresholds=None)
    types = {a.type for a in alerts}
    assert "LOW_GENERATION" in types
    assert "HIGH_GENERATION" in types
    assert "RAMP" in types
    for a in alerts:
        if a.type == "LOW_GENERATION":
            assert "4.0 MW" in a.message
        elif a.type == "HIGH_GENERATION":
            assert "34.0 MW" in a.message
        elif a.type == "RAMP":
            assert "20.0 MW" in a.message


def test_alert_skill_unaffected():
    idx = pd.date_range("2024-05-01 00:00", periods=4, freq="h", tz="UTC")
    actual = pd.Series([1.0, 2.0, 5.0, 10.0], index=idx)
    # Target hours 0 and 1 flagged
    flagged = pd.Series([True, True, False, False], index=idx)
    res = alert_skill(flagged, actual, "LOW_GENERATION", 3.0)
    assert res["precision"] == pytest.approx(1.0)
    assert res["recall"] == pytest.approx(1.0)
    assert res["alert_hours"] == 2
    assert res["event_hours"] == 2


def test_hybrid_trust_score():
    # 1. Weights: w_s = 10, w_w = 30 -> (10*80 + 30*40) / 40 = 2000 / 40 = 50.0
    s_weighted = hybrid_trust_score(10.0, 30.0, 80.0, 40.0)
    assert s_weighted == 50.0

    # 2. Both-zero fallback (< 1e-6) -> (80 + 40) / 2 = 60.0
    s_zero = hybrid_trust_score(0.0, 0.0, 80.0, 40.0)
    assert s_zero == 60.0

    # Near-zero fallback (< 1e-6)
    s_near_zero = hybrid_trust_score(1e-8, 1e-8, 80.0, 40.0)
    assert s_near_zero == 60.0

    # 3. Bounds 0..100
    assert hybrid_trust_score(10.0, 20.0, 100.0, 100.0) == 100.0
    assert hybrid_trust_score(10.0, 20.0, 0.0, 0.0) == 0.0

    # 4. Vector inputs
    qs = np.array([10.0, 0.0, 20.0])
    qw = np.array([30.0, 0.0, 20.0])
    ts = np.array([80.0, 80.0, 70.0])
    tw = np.array([40.0, 40.0, 30.0])
    res = hybrid_trust_score(qs, qw, ts, tw)
    np.testing.assert_array_equal(res, np.array([50.0, 60.0, 50.0]))


def test_low_confidence_alert_numeric_context(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=3, freq="h", tz="UTC")
    q_data = [
        [5.0, 10.0, 15.0, 20.0, 25.0],
        [5.0, 10.0, 15.0, 20.0, 25.0],
        [5.0, 10.0, 15.0, 20.0, 25.0],
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    trust = pd.Series([25.0, 30.0, 80.0], index=idx)
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], trust=trust)
    conf_alerts = [a for a in alerts if a.type == "LOW_CONFIDENCE"]
    assert len(conf_alerts) == 1
    # Min trust in the window is 25, threshold is cfg.alerts.low_trust_score (40)
    assert f"trust score 25 < {cfg.alerts.low_trust_score:.0f}" in conf_alerts[0].message

