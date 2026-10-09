"""Test Chronos-2 covariate framing for strict zero-leakage compliance (no torch required)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from terra.models.chronos2 import COVARIATES, build_inputs
from terra.schema import LEAD_BUCKETS, TARGETS


@pytest.fixture
def fake_dataset() -> pd.DataFrame:
    """Create a synthetic dataset where every source, lead prefix, and timestamp has distinct values."""
    n_hours = 120
    idx = pd.date_range("2026-01-01 00:00", periods=n_hours, freq="h", tz="UTC")
    hours = np.arange(n_hours)

    data: dict[str, np.ndarray] = {
        TARGETS["solar"]: 1000.0 + hours,
        TARGETS["wind"]: 2000.0 + hours,
    }

    # Distinct sentinels for each prefix:
    # act_ -> 800_000 (NEVER to be used)
    # fx0_ -> 900_000 (NEVER to be used as lead feature)
    # fx1_ -> 100_000 (Day-ahead lead 1-24)
    # fx2_ -> 200_000 (Two-day-ahead lead 25-48)
    prefixes = {
        "act_": 800_000.0,
        "fx0_": 900_000.0,
        "fx1_": 100_000.0,
        "fx2_": 200_000.0,
    }
    for pfx, base in prefixes.items():
        for c in COVARIATES:
            data[f"{pfx}{c}"] = base + hours

    for d, base in [("0", 950_000.0), ("1", 150_000.0), ("2", 250_000.0)]:
        data[f"phys{d}_solar_mw"] = base + hours
        data[f"phys{d}_wind_mw"] = base + 5000.0 + hours

    return pd.DataFrame(data, index=idx)


def test_chronos2_covariates_no_leakage(fake_dataset: pd.DataFrame) -> None:
    """Verify context and future covariates strictly obey leak-free framing."""
    ds = fake_dataset
    # Pick issue time at index 48 (2026-01-03 00:00 UTC)
    t0 = ds.index[48]
    context_h = 24
    horizon_h = 48

    ctx, fut = build_inputs(ds, "solar", pd.DatetimeIndex([t0]), context_h=context_h, horizon_h=horizon_h)

    # 1. Context timestamps must be strictly <= t0
    ctx_timestamps = pd.to_datetime(ctx["timestamp"]).dt.tz_localize("UTC")
    assert (ctx_timestamps <= t0).all(), "Context contains timestamps strictly after issue time!"
    assert ctx_timestamps.max() == t0, "Context must end exactly at issue time t0"
    assert len(ctx) == context_h

    # 2. Context target values must come from history <= t0
    expected_targets = ds[TARGETS["solar"]].loc[ctx_timestamps].to_numpy()
    np.testing.assert_array_equal(ctx["target"].to_numpy(), expected_targets)

    # 3. Context covariates must use fx1_ (day-ahead past) and NEVER fx0_ or act_
    for c in COVARIATES:
        vals = ctx[c].to_numpy()
        assert not np.any((vals >= 800_000.0) & (vals < 900_000.0)), f"act_ found in context cov {c}"
        assert not np.any(vals >= 900_000.0), f"fx0_ found in context cov {c}"
        expected_past = ds[f"fx1_{c}"].loc[ctx_timestamps].to_numpy()
        np.testing.assert_array_equal(vals, expected_past)

    expected_past_phys = ds["phys1_solar_mw"].loc[ctx_timestamps].to_numpy()
    np.testing.assert_array_equal(ctx["phys"].to_numpy(), expected_past_phys)

    # 4. Future covariates must respect LEAD_BUCKETS
    assert len(fut) == horizon_h
    fut_timestamps = pd.to_datetime(fut["timestamp"]).dt.tz_localize("UTC")
    leads = ((fut_timestamps - t0) / pd.Timedelta(hours=1)).astype(int).to_numpy()
    np.testing.assert_array_equal(leads, np.arange(1, horizon_h + 1))

    # Verify leads 1-24 use fx1_ and leads 25-48 use fx2_
    for i, lead in enumerate(leads):
        ts = fut_timestamps.iloc[i]
        bucket_prefix = next(p for lo, hi, _, p in LEAD_BUCKETS if lo <= lead <= hi)
        d = bucket_prefix[2]
        assert bucket_prefix in ("fx1_", "fx2_")

        for c in COVARIATES:
            fut_val = fut.iloc[i][c]
            expected_val = ds[f"{bucket_prefix}{c}"].loc[ts]
            forbidden_act = ds[f"act_{c}"].loc[ts]
            forbidden_fx0 = ds[f"fx0_{c}"].loc[ts]

            assert fut_val == expected_val, f"Lead {lead} covariate {c} did not match {bucket_prefix}"
            assert fut_val != forbidden_act, f"Lead {lead} covariate {c} leaked act_ value!"
            assert fut_val != forbidden_fx0, f"Lead {lead} covariate {c} leaked fx0_ value!"

        fut_phys = fut.iloc[i]["phys"]
        expected_phys = ds[f"phys{d}_solar_mw"].loc[ts]
        assert fut_phys == expected_phys


def test_chronos2_no_cross_item_leakage(fake_dataset: pd.DataFrame) -> None:
    """Verify that multiple issues in a batch do not cross-leak via forward/backward filling."""
    ds = fake_dataset.copy()
    t0 = ds.index[48]
    t1 = ds.index[72]

    # Insert a NaN at the very end of t0's context in ds
    ds.loc[t0, "fx1_ghi"] = np.nan

    ctx, _ = build_inputs(ds, "solar", pd.DatetimeIndex([t0, t1]), context_h=12, horizon_h=24)

    item0_ctx = ctx[ctx["item_id"] == t0.strftime("%Y-%m-%dT%H")]
    item1_ctx = ctx[ctx["item_id"] == t1.strftime("%Y-%m-%dT%H")]

    # In item0, the NaN at t0 should have been forward-filled from t0 - 1h (its own history),
    # NOT from item1's first row (which is from 24h later in the future!)
    t0_minus_1 = t0 - pd.Timedelta(hours=1)
    expected_fill_val = fake_dataset.loc[t0_minus_1, "fx1_ghi"]
    item0_t0_val = item0_ctx.iloc[-1]["ghi"]

    assert item0_t0_val == expected_fill_val, "NaN was not filled from within item's own context history!"
    assert item0_t0_val != item1_ctx.iloc[0]["ghi"], "Cross-item leakage detected in context fill!"
