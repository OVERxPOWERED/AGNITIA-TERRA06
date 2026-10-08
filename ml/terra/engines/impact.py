"""Impact engine: turn value-of-forecast and DSM results into headline impact numbers."""
from __future__ import annotations

import pandas as pd

from terra.config import TerraConfig


def impact_summary(vof: pd.DataFrame, cfg: TerraConfig, dsm: pd.DataFrame | None = None,
                   ours: str = "ensemble", baseline: str = "persistence", days: float | None = None) -> dict:
    """Compare TERRA (ensemble-planned) with persistence-planned dispatch over the test period."""
    v = vof.set_index("strategy")
    b, o = v.loc[baseline], v.loc[ours]
    backup_avoided = float(b["backup_mwh"] - o["backup_mwh"])
    out = {
        "period_days": days,
        "backup_avoided_mwh": round(backup_avoided, 1),
        "co2_avoided_t": round(backup_avoided * cfg.costs.emission_factor_t_per_mwh, 1),
        "curtailment_avoided_mwh": round(float(b["curtail_mwh"] - o["curtail_mwh"]), 1),
        "cost_saved_inr": round(float(b["cost_inr"] - o["cost_inr"]), 0),
        "battery_vs_no_battery_backup_avoided_mwh": round(float(v.loc["no_battery", "backup_mwh"] - o["backup_mwh"]), 1),
        "emission_factor_t_per_mwh": cfg.costs.emission_factor_t_per_mwh,
        "emission_factor_source": cfg.costs.emission_factor_source,
        "plant_capacity_mw": cfg.capacity_mw("hybrid"),
    }
    if dsm is not None and {"strategy", "charge_inr"} <= set(dsm.columns):
        d = dsm.groupby("strategy")["charge_inr"].sum()
        if "persistence" in d and "terra_optimized" in d:
            out["dsm_charges_saved_inr"] = round(float(d["persistence"] - d["terra_optimized"]), 0)
    return out


def scale_to_capacity(summary: dict, target_mw: float) -> dict:
    """Linear extrapolation to a larger fleet — ALWAYS label as an extrapolation in UI/report."""
    f = target_mw / summary["plant_capacity_mw"]
    keys = ("backup_avoided_mwh", "co2_avoided_t", "curtailment_avoided_mwh", "cost_saved_inr", "dsm_charges_saved_inr")
    return {k: round(summary[k] * f, 1) for k in keys if k in summary} | {"target_mw": target_mw, "extrapolation": True}
