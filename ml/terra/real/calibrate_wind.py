"""Calibrate the wind twin on real turbine SCADA (R2): empirical power curve, scatter, availability."""
from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from terra.logs import get_logger
from terra.paths import CONFIG_DIR
from terra.real.calibrate_solar import _append_doc
from terra.real.loaders import load_wind_scada

log = get_logger(__name__)


def empirical_curve(df: pd.DataFrame, rated_kw: float, bin_ms: float = 0.5) -> pd.DataFrame:
    ok = df[(df["power_kw"] > 0) | (df["ws_ms"] < 3.5)]              # drop obvious downtime
    bins = np.arange(0, 26 + bin_ms, bin_ms)
    cut = pd.cut(ok["ws_ms"], bins)
    g = (ok["power_kw"] / rated_kw).groupby(cut, observed=False)
    curve = pd.DataFrame({"ws_ms": bins[:-1] + bin_ms / 2, "p_frac_median": g.median().to_numpy(),
                          "p_frac_std": g.std().to_numpy(), "n": g.size().to_numpy()})
    return curve[curve["n"] >= 10].reset_index(drop=True)


def run() -> dict:
    df = load_wind_scada()
    rated = float(df["theoretical_kw"].max())
    curve = empirical_curve(df, rated)
    frac_curve = np.interp(df["ws_ms"], curve["ws_ms"], curve["p_frac_median"].fillna(0))
    resid = pd.Series(df["power_kw"].to_numpy() / rated - frac_curve, index=df.index)
    hourly = resid.resample("h").mean().dropna()
    phi = float(np.clip(hourly.autocorr(1), 0, 0.95))
    sigma = float(np.clip(hourly.std() * np.sqrt(1 - phi**2), 0.01, 0.3))
    down = ((df["ws_ms"] > 4) & (df["power_kw"] <= 0)).astype(int)
    starts = int((down.diff() == 1).sum())
    days = (df.index.max() - df.index.min()).days or 1
    curtailed = (df["ws_ms"] > 13) & (df["power_kw"] < 0.8 * df["theoretical_kw"]) & (df["power_kw"] > 0)
    out = {
        "source": "Kaggle wind turbine SCADA (Turkey, 2018, 10-min)", "rated_kw": rated,
        "recommended": {"ar1_phi": phi, "ar1_sigma": sigma, "outage_rate_per_day": starts / days,
                        "outage_mean_hours": float(down.sum() / max(starts, 1) / 6),
                        "curtail_fraction_of_time_above_13ms": float(curtailed.mean())},
    }
    (CONFIG_DIR / "calibration").mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "calibration" / "wind.yaml").write_text(yaml.safe_dump(out, sort_keys=False))
    curve.to_csv(CONFIG_DIR / "calibration" / "wind_curve.csv", index=False)
    _append_doc(["## Wind calibration (R2)", "", "Empirical power curve (fraction of rated):", "",
                 curve.round(3).to_markdown(index=False), "", "Recommended realism values:", "", "```yaml",
                 yaml.safe_dump(out["recommended"], sort_keys=False), "```", ""])
    log.info("wind calibration: %s", out["recommended"])
    return out
