import numpy as np
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
    for lead, prefix in ((5, "fx1_"), (20, "fx1_"), (25, "fx2_"), (45, "fx2_")):
        row = f[f["lead_h"] == lead].iloc[10]
        assert row["fx_t2m"] == pytest.approx(ds.loc[row["target_time_utc"], f"{prefix}t2m"])


def test_weather_lead_leakage_and_coverage(frames, ds):
    """Leakage test independent of mapping table: for lead L in 1..48, forecast lead in hours

    of the prefix (fx0=0, fx1=24, fx2=48) >= L for every L, and fx0 must not be selected at all.
    Bucket labels must cover leads 1..48 exactly once with no gaps or overlaps.
    """
    prefix_horizons = {"fx0_": 0, "fx1_": 24, "fx2_": 48}
    bucket_coverage: dict[str, list[int]] = {}

    for source in ("solar", "wind"):
        f = frames[source]
        for lead in range(1, 49):
            sub = f[f["lead_h"] == lead]
            assert not sub.empty, f"Missing rows for {source} lead {lead}"

            row = sub.iloc[0]
            target_ts = row["target_time_utc"]

            matched = [
                p for p in ("fx0_", "fx1_", "fx2_")
                if np.isclose(row["fx_t2m"], ds.loc[target_ts, f"{p}t2m"])
            ]
            assert len(matched) == 1, f"Expected unique prefix match for {source} lead {lead}, found {matched}"
            chosen_prefix = matched[0]

            assert chosen_prefix != "fx0_", f"{source} lead {lead} used fx0_ (look-ahead leak)"
            assert prefix_horizons[chosen_prefix] >= lead, (
                f"{source} lead {lead} leakage: prefix horizon {prefix_horizons[chosen_prefix]}h < lead {lead}h"
            )

            if source == "solar":
                bucket = row["lead_bucket"]
                bucket_coverage.setdefault(bucket, []).append(lead)

    all_leads = []
    for bucket, leads in bucket_coverage.items():
        assert leads == list(range(min(leads), max(leads) + 1)), f"Bucket {bucket} has internal gaps: {leads}"
        all_leads.extend(leads)

    assert len(all_leads) == 48, f"Expected 48 lead assignments, got {len(all_leads)}"
    assert sorted(all_leads) == list(range(1, 49)), "Bucket labels do not partition 1..48 exactly once"


def test_splits_do_not_cross(frames, cfg):
    b = cfg.splits.bounds()
    for f in frames.values():
        for name, (lo, hi) in b.items():
            part = f[f["split"] == name]
            assert part["target_time_utc"].max() <= hi and part["issue_time_utc"].min() >= lo


def test_tune_holdout_split_no_leakage(frames):
    from terra.pipelines.train import split_train_holdout

    for source in ("solar", "wind"):
        f = frames[source]
        fit_df, holdout_df = split_train_holdout(f, holdout_frac=0.2)
        assert not fit_df.empty and not holdout_df.empty
        # No leakage: tune_holdout issue times strictly after the fitted part
        assert holdout_df["issue_time_utc"].min() > fit_df["issue_time_utc"].max()
        # Boundary rows dropped: fit target times never reach or cross into holdout issue times
        assert fit_df["target_time_utc"].max() < holdout_df["issue_time_utc"].min()
        # Verify boundary rows were indeed dropped
        tr = f[f["split"] == "train"]
        issues = np.sort(tr["issue_time_utc"].unique())
        cut = issues[int(len(issues) * 0.8)]
        boundary_rows = tr[(tr["issue_time_utc"] < cut) & (tr["target_time_utc"] >= cut)]
        assert len(boundary_rows) > 0
        assert len(fit_df) + len(holdout_df) + len(boundary_rows) == len(tr)
