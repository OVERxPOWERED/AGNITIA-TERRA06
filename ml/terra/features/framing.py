"""Turn the hourly dataset into supervised forecast rows (issue_time, target_time, lead_h).

Leakage rules enforced here:
- weather features come from the lead-appropriate forecast column (fx0/fx1/fx2), never act_*
- generation history uses only values at or before issue_time
- the split is assigned by issue_time and rows whose target crosses a split boundary are dropped
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from terra.config import TerraConfig
from terra.schema import CAL, FX, HIST, LEAD_BUCKETS, PHYS, TARGETS

WEATHER_FEATURES = ("ghi", "dni", "dhi", "cloud", "t2m", "rh2m", "psfc", "ws10", "ws100",
                    "wd100_sin", "wd100_cos", "rho", "shear", "precip")


def issue_times(index: pd.DatetimeIndex, hours_utc: list[int], horizon_h: int = 48,
                history_h: int = 7 * 24) -> pd.DatetimeIndex:
    """Issue times at the given UTC hours with enough history before and horizon after."""
    first, last = index[0] + pd.Timedelta(hours=history_h), index[-1] - pd.Timedelta(hours=horizon_h)
    cand = index[(index >= first) & (index <= last)]
    return cand[cand.hour.isin(hours_utc)]


def assign_split(times: pd.DatetimeIndex, cfg: TerraConfig) -> np.ndarray:
    out = np.full(len(times), "none", dtype=object)
    for name, (lo, hi) in cfg.splits.bounds().items():
        out[(times >= lo) & (times <= hi)] = name
    return out


def history_features(y: pd.Series, phys0: pd.Series) -> pd.DataFrame:
    """Per-timestamp history stats; looked up at issue_time (so only past data is used)."""
    resid = y - phys0
    return pd.DataFrame({
        "hist_last": y,
        "hist_mean24": y.rolling(24, min_periods=1).mean(),
        "hist_max24": y.rolling(24, min_periods=1).max(),
        "hist_resid_mean24": resid.rolling(24, min_periods=1).mean(),
        "hist_resid_mean168": resid.rolling(168, min_periods=1).mean(),
        "hist_absresid_mean168": resid.abs().rolling(168, min_periods=1).mean(),   # also used by Trust
    }, index=y.index)


def calendar_features(times: pd.DatetimeIndex, ds: pd.DataFrame) -> pd.DataFrame:
    ist = times.tz_convert("Asia/Kolkata")
    h = ist.hour.to_numpy(float)
    doy = ist.dayofyear.to_numpy(float)
    cs = ds["cs_ghi"].reindex(times).to_numpy()
    zen = ds["zenith"].reindex(times).to_numpy()
    return pd.DataFrame({
        f"{CAL}hour_sin": np.sin(2 * np.pi * h / 24), f"{CAL}hour_cos": np.cos(2 * np.pi * h / 24),
        f"{CAL}doy_sin": np.sin(2 * np.pi * doy / 365.25), f"{CAL}doy_cos": np.cos(2 * np.pi * doy / 365.25),
        f"{CAL}weekday": ist.dayofweek.to_numpy(), f"{CAL}cs_ghi": cs, f"{CAL}zenith": zen,
        f"{CAL}is_day": (zen < 90).astype(int),
    })


def frame_source(ds: pd.DataFrame, source: str, cfg: TerraConfig, issues: pd.DatetimeIndex,
                 horizon_h: int | None = None, require_target: bool = True) -> pd.DataFrame:
    """Build the framed table for one source ('solar' | 'wind').

    `require_target=False` allows framing future targets (live forecasting) where y is unknown.
    """
    horizon_h = horizon_h or cfg.forecast.horizon_h
    ycol = TARGETS[source]
    y = ds[ycol]
    hist = history_features(y, ds[f"phys0_{source}_mw"])
    hist_at_issue = hist.reindex(issues).reset_index(drop=True)
    split = assign_split(issues, cfg)
    frames = []
    for lead in range(1, horizon_h + 1):
        prefix = next(p for lo, hi, _, p in LEAD_BUCKETS if lo <= lead <= hi)
        d = prefix[2]                                                   # "0" | "1" | "2"
        bucket = next(b for lo, hi, b, _ in LEAD_BUCKETS if lo <= lead <= hi)
        targets = issues + pd.Timedelta(hours=lead)
        part = pd.DataFrame({"issue_time_utc": issues, "target_time_utc": targets,
                             "lead_h": lead, "lead_bucket": bucket, "split": split})
        wx = ds.reindex(targets)
        for v in WEATHER_FEATURES:
            part[f"{FX}{v}"] = wx[f"{prefix}{v}"].to_numpy()
        part[f"{PHYS}mw"] = wx[f"phys{d}_{source}_mw"].to_numpy()
        cal = calendar_features(targets, ds)
        part = pd.concat([part, cal], axis=1)
        # same hour on the most recent fully observed day: lag = 24 * ceil(lead / 24)
        lag = 24 * int(np.ceil(lead / 24))
        part[f"{HIST}lag_day"] = y.reindex(targets - pd.Timedelta(hours=lag)).to_numpy()
        part[f"{HIST}lag_week_mean"] = np.nanmean(np.stack(
            [y.reindex(targets - pd.Timedelta(hours=lag + 24 * k)).to_numpy() for k in range(7)]), axis=0)
        part = pd.concat([part, hist_at_issue], axis=1)
        part["y"] = y.reindex(targets).to_numpy()
        target_split = assign_split(pd.DatetimeIndex(targets), cfg)
        part = part[(part["split"] == target_split) | (not require_target)]
        frames.append(part)
    out = pd.concat(frames, ignore_index=True)
    # derived forecast features
    cs = out[f"{CAL}cs_ghi"].to_numpy()
    out[f"{FX}csi"] = np.where(cs > 20, out[f"{FX}ghi"] / np.maximum(cs, 1e-6), 0.0).clip(0, 1.5)
    out[f"{FX}ws100_cubed"] = out[f"{FX}ws100"] ** 3
    out["capacity_mw"] = cfg.capacity_mw(source)
    out["source"] = source
    if require_target:
        out = out[(out["split"] != "none") & out["y"].notna()]
    return out.reset_index(drop=True)


def frame_all(ds: pd.DataFrame, cfg: TerraConfig, issue_hours: list[int] | None = None) -> dict[str, pd.DataFrame]:
    issues = issue_times(ds.index, issue_hours or cfg.forecast.train_issue_hours_utc, cfg.forecast.horizon_h)
    return {s: frame_source(ds, s, cfg, issues) for s in ("solar", "wind")}
