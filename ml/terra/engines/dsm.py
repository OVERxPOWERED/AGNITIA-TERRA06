"""H5 Deviation Shield: estimate DSM deviation charges for a 15-minute schedule vs actual.

Deviation % per block = 100 * (actual - schedule) / denominator
denominator = X * available_capacity + (1 - X) * schedule        (X from config/dsm.yaml)
Within ±tolerance: no charge. Beyond tolerance: slab rates (₹/kWh) on the energy beyond tolerance.
Rates in config/dsm.yaml are ILLUSTRATIVE until verified against the regulation (task T5.7.1).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from terra.config import load_yaml
from terra.schema import QCOLS, QUANTILES


@dataclass
class DsmProfile:
    tolerance_pct: dict[str, float]
    x_factor: dict[str, float]
    slabs: list[dict]
    illustrative: bool
    block_hours: float = 0.25

    @classmethod
    def load(cls, name: str = "dsm.yaml") -> "DsmProfile":
        y = load_yaml(name)
        return cls(y["tolerance_pct"], y["x_factor"], y["slabs"], bool(y.get("illustrative", True)),
                   y.get("block_minutes", 15) / 60)


def deviation_charges(schedule_mw: np.ndarray, actual_mw: np.ndarray, avc_mw: float, source: str,
                      prof: DsmProfile) -> pd.DataFrame:
    x = prof.x_factor[source]
    tol = prof.tolerance_pct[source]
    denom = np.maximum(x * avc_mw + (1 - x) * schedule_mw, 1e-3)
    dev_mw = actual_mw - schedule_mw
    dev_pct = 100 * dev_mw / denom
    beyond = np.maximum(np.abs(dev_pct) - tol, 0.0)                 # % points beyond tolerance
    charge = np.zeros_like(beyond)
    lower = 0.0
    for slab in prof.slabs:                                         # allocate beyond-% across slabs
        upper = float(slab["upto_pct"])
        part = np.clip(beyond - lower, 0, upper - lower)
        kwh = part / 100 * denom * prof.block_hours * 1000
        charge += kwh * float(slab["inr_per_kwh"])
        lower = upper
    return pd.DataFrame({"schedule_mw": schedule_mw, "actual_mw": actual_mw, "deviation_mw": dev_mw,
                         "deviation_pct": dev_pct, "beyond_tolerance_pct": beyond, "charge_inr": charge})


def schedule_at_level(q: np.ndarray, tau: float) -> np.ndarray:
    """Interpolate a schedule at quantile level tau from rows of (q05..q95)."""
    return np.array([np.interp(tau, QUANTILES, row) for row in q])


def choose_level(q_blocks: np.ndarray, actual_blocks: np.ndarray, avc: float, source: str, prof: DsmProfile,
                 grid: np.ndarray | None = None) -> tuple[float, pd.DataFrame]:
    """Pick the quantile level that minimises total charges (fit on VALIDATION blocks only)."""
    grid = np.round(np.arange(0.30, 0.701, 0.05), 2) if grid is None else grid
    res = [(t, deviation_charges(schedule_at_level(q_blocks, t), actual_blocks, avc, source, prof)["charge_inr"].sum())
           for t in grid]
    table = pd.DataFrame(res, columns=["level", "charge_inr"])
    return float(table.loc[table["charge_inr"].idxmin(), "level"]), table


def schedule_csv(blocks_mw: pd.Series) -> str:
    """Day-ahead schedule export: one row per 15-min block in IST (block 1 = 00:00-00:15)."""
    ist_end = blocks_mw.index.tz_convert("Asia/Kolkata")
    ist_start = ist_end - pd.Timedelta(minutes=15)
    df = pd.DataFrame({"block_no": (ist_start.hour * 4 + ist_start.minute // 15 + 1),
                       "start_ist": ist_start.strftime("%Y-%m-%d %H:%M"), "end_ist": ist_end.strftime("%H:%M"),
                       "schedule_mw": blocks_mw.round(3).to_numpy()})
    return df.to_csv(index=False)


QCOL_LIST = list(QCOLS)
