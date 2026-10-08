import pandas as pd
import pytest

from terra.data.quality import assert_no_leakage
from terra.features.build_features import feature_columns


def test_no_actual_weather_in_features(frames):
    for f in frames.values():
        cols = feature_columns(f)
        assert not any(c.startswith("act_") for c in cols)
        assert "y" not in cols


def test_leakage_guard_raises():
    with pytest.raises(AssertionError):
        assert_no_leakage(["fx_ghi", "act_ghi"])


def test_history_lag_is_before_issue(frames, ds):
    f = frames["wind"]
    row = f[f["lead_h"] == 30].iloc[0]
    lag_time = row["target_time_utc"] - pd.Timedelta(hours=48)
    assert lag_time <= row["issue_time_utc"]
    assert row["hist_lag_day"] == pytest.approx(ds.loc[lag_time, "wind_mw"])


def test_lead_uses_correct_forecast_column(frames, ds):
    f = frames["solar"]
    for lead, prefix in ((5, "fx0_"), (20, "fx1_"), (45, "fx2_")):
        row = f[f["lead_h"] == lead].iloc[10]
        assert row["fx_t2m"] == pytest.approx(ds.loc[row["target_time_utc"], f"{prefix}t2m"])


def test_splits_do_not_cross(frames, cfg):
    b = cfg.splits.bounds()
    for f in frames.values():
        for name, (lo, hi) in b.items():
            part = f[f["split"] == name]
            assert part["target_time_utc"].max() <= hi and part["issue_time_utc"].min() >= lo
