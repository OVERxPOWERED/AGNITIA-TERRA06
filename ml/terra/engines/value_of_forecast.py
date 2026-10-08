"""Value of forecast: plan the battery with each model's forecast, settle against ACTUAL generation.

Turns forecast accuracy into backup MWh, rupees and tCO2 — the key impact numbers.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from terra.config import TerraConfig
from terra.engines.dispatch import kpis, no_battery, plan, settle
from terra.engines.hybrid import combine
from terra.schema import QCOLS

KEYS = ["issue_time_utc", "target_time_utc", "lead_h"]


def hybrid_long(preds_solar: pd.DataFrame, preds_wind: pd.DataFrame, model: str, rho_by_day: dict[int, float],
                cfg: TerraConfig, issue_hour: int | None = None, max_lead: int | None = None) -> pd.DataFrame:
    """Combine one model's solar and wind long predictions into hybrid quantiles + actual."""
    s = preds_solar[preds_solar["model"] == model]
    w = preds_wind[preds_wind["model"] == model]
    if issue_hour is not None:
        s = s[s["issue_time_utc"].dt.hour == issue_hour]
        w = w[w["issue_time_utc"].dt.hour == issue_hour]
    if max_lead is not None:
        s, w = s[s["lead_h"] <= max_lead], w[w["lead_h"] <= max_lead]
    m = s.merge(w, on=KEYS, suffixes=("_s", "_w"))
    rho = np.array([rho_by_day.get(int(d), 0.0) for d in m["cal_is_day_s"]])
    q = combine(m[[f"{c}_s" for c in QCOLS]].to_numpy(), m[[f"{c}_w" for c in QCOLS]].to_numpy(),
                cfg.capacity_mw("solar"), cfg.capacity_mw("wind"), rho, n_samples=500)
    out = m[KEYS].copy()
    out[list(QCOLS)] = q
    out["y"] = m["y_s"].to_numpy() + m["y_w"].to_numpy()
    out["cal_is_day"] = m["cal_is_day_s"].to_numpy()
    out["model"] = model
    return out.sort_values(KEYS).reset_index(drop=True)


def run_value_of_forecast(hybrid_by_model: dict[str, pd.DataFrame], demand: pd.Series, cfg: TerraConfig,
                          horizon_h: int = 24) -> pd.DataFrame:
    """Daily rolling plan (one issue per day), SoC carried forward from the settled result."""
    rows = []
    any_df = next(iter(hybrid_by_model.values()))
    strategies = {**hybrid_by_model, "perfect_foresight": any_df.assign(q50=any_df["y"], q10=any_df["y"])}
    for name, df in strategies.items():
        d = df[df["lead_h"] <= horizon_h]
        soc = None
        settled_all = []
        for _, g in d.groupby("issue_time_utc"):
            g = g.sort_values("lead_h")
            dem = demand.reindex(g["target_time_utc"]).to_numpy()
            res = plan(g["q50"].to_numpy(), dem, cfg.battery, cfg.costs, g["q10"].to_numpy(), soc,
                       index=pd.DatetimeIndex(g["target_time_utc"]))
            st = settle(res.schedule, g["y"].to_numpy(), cfg.costs)
            soc = float(st["soc_mwh"].iloc[-1])
            settled_all.append(st)
        k = kpis(pd.concat(settled_all), cfg.costs)
        rows.append({"strategy": name, **k})
    # reference: no battery at all
    d = any_df[any_df["lead_h"] <= horizon_h]
    nb = no_battery(d["y"].to_numpy(), demand.reindex(d["target_time_utc"]).to_numpy(), cfg.costs)
    rows.append({"strategy": "no_battery", **nb.kpis})
    return pd.DataFrame(rows)
