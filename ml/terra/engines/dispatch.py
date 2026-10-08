"""H2 Battery Dispatch Advisor: linear program over the forecast horizon.

Energy balance each hour t (MW, 1-hour steps):
    gen_t - curt_t - ch_t + dis_t + backup_t = demand_t
    soc_t = soc_{t-1} + eta * ch_t - dis_t / eta            (eta = sqrt(round-trip efficiency))
    soc_t >= soc_min + reserve_t                            (reserve for the P10 scenario)
Objective: backup_cost * backup + curtail_penalty * curt + degradation * (ch + dis)
Variables are ordered [ch(T), dis(T), soc(T), backup(T), curt(T)].
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import eye, hstack, lil_matrix, vstack

from terra.config import BatteryCfg, CostsCfg


@dataclass
class DispatchResult:
    schedule: pd.DataFrame          # ch, dis, soc, backup, curt (MW / MWh)
    kpis: dict[str, float]
    status: str


def plan(gen_p50: np.ndarray, demand: np.ndarray, bat: BatteryCfg, costs: CostsCfg,
         gen_p10: np.ndarray | None = None, soc0_mwh: float | None = None,
         index: pd.Index | None = None) -> DispatchResult:
    T = len(gen_p50)
    eta = np.sqrt(bat.round_trip_eff)
    smin, smax = bat.soc_min_frac * bat.energy_mwh, bat.soc_max_frac * bat.energy_mwh
    soc0 = bat.soc_init_frac * bat.energy_mwh if soc0_mwh is None else float(np.clip(soc0_mwh, smin, smax))
    # reserve: keep energy to cover next hour's (P50 - P10) shortfall, capped by usable energy
    if gen_p10 is not None:
        short = np.maximum(gen_p50 - gen_p10, 0.0)
        reserve = np.minimum(bat.reserve_factor * np.append(short[1:], 0.0), smax - smin)
    else:
        reserve = np.zeros(T)

    n = 5 * T
    Id = eye(T, format="csr")
    Z = lil_matrix((T, T)).tocsr()
    # balance: -ch + dis + backup - curt = demand - gen
    A_bal = hstack([-Id, Id, Z, Id, -Id])
    b_bal = demand - gen_p50
    # soc dynamics: soc_t - soc_{t-1} - eta ch_t + dis_t/eta = 0 (soc_{-1} = soc0)
    D = lil_matrix((T, T))
    for t in range(T):
        D[t, t] = 1.0
        if t > 0:
            D[t, t - 1] = -1.0
    A_soc = hstack([-eta * Id, (1 / eta) * Id, D.tocsr(), Z, Z])
    b_soc = np.zeros(T)
    b_soc[0] = soc0
    A_eq = vstack([A_bal, A_soc]).tocsr()
    b_eq = np.concatenate([b_bal, b_soc])
    c = np.concatenate([
        np.full(T, bat.degradation_inr_per_mwh / 2), np.full(T, bat.degradation_inr_per_mwh / 2),
        np.zeros(T), np.full(T, costs.backup_inr_per_mwh), np.full(T, costs.curtail_penalty_inr_per_mwh)])
    bounds = ([(0, bat.power_mw)] * T + [(0, bat.power_mw)] * T +
              [(min(smin + reserve[t], smax), smax) for t in range(T)] +
              [(0, None)] * T + [(0, max(g, 0.0)) for g in gen_p50])
    res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if res.status != 0:   # infeasible reserve -> retry without reserve
        bounds[2 * T:3 * T] = [(smin, smax)] * T
        res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    x = res.x if res.x is not None else np.zeros(n)
    sched = pd.DataFrame({"gen_mw": gen_p50, "demand_mw": demand, "charge_mw": x[:T], "discharge_mw": x[T:2 * T],
                          "soc_mwh": x[2 * T:3 * T], "backup_mw": x[3 * T:4 * T], "curtail_mw": x[4 * T:]},
                         index=index if index is not None else pd.RangeIndex(T))
    return DispatchResult(sched, kpis(sched, costs), res.message)


def rule_based(gen: np.ndarray, demand: np.ndarray, bat: BatteryCfg, costs: CostsCfg,
               soc0_mwh: float | None = None, index: pd.Index | None = None) -> DispatchResult:
    """Greedy: charge with surplus, discharge on deficit."""
    eta = np.sqrt(bat.round_trip_eff)
    smin, smax = bat.soc_min_frac * bat.energy_mwh, bat.soc_max_frac * bat.energy_mwh
    soc = bat.soc_init_frac * bat.energy_mwh if soc0_mwh is None else soc0_mwh
    rows = []
    for g, d in zip(gen, demand):
        surplus = g - d
        ch = dis = backup = curt = 0.0
        if surplus > 0:
            ch = min(surplus, bat.power_mw, (smax - soc) / eta)
            curt = surplus - ch
        else:
            dis = min(-surplus, bat.power_mw, (soc - smin) * eta)
            backup = -surplus - dis
        soc = soc + eta * ch - dis / eta
        rows.append((g, d, ch, dis, soc, backup, curt))
    sched = pd.DataFrame(rows, columns=["gen_mw", "demand_mw", "charge_mw", "discharge_mw", "soc_mwh",
                                        "backup_mw", "curtail_mw"],
                         index=index if index is not None else pd.RangeIndex(len(gen)))
    return DispatchResult(sched, kpis(sched, costs), "rule")


def no_battery(gen: np.ndarray, demand: np.ndarray, costs: CostsCfg, index: pd.Index | None = None) -> DispatchResult:
    sched = pd.DataFrame({"gen_mw": gen, "demand_mw": demand, "charge_mw": 0.0, "discharge_mw": 0.0, "soc_mwh": 0.0,
                          "backup_mw": np.maximum(demand - gen, 0), "curtail_mw": np.maximum(gen - demand, 0)},
                         index=index if index is not None else pd.RangeIndex(len(gen)))
    return DispatchResult(sched, kpis(sched, costs), "none")


def settle(planned: pd.DataFrame, actual_gen: np.ndarray, costs: CostsCfg) -> pd.DataFrame:
    """Apply the planned battery moves to ACTUAL generation; backup/curtailment absorb the error."""
    s = planned.copy()
    net = actual_gen - s["charge_mw"].to_numpy() + s["discharge_mw"].to_numpy() - s["demand_mw"].to_numpy()
    s["gen_mw"] = actual_gen
    s["backup_mw"] = np.maximum(-net, 0)
    s["curtail_mw"] = np.maximum(net, 0)
    return s


def kpis(s: pd.DataFrame, costs: CostsCfg) -> dict[str, float]:
    backup = float(s["backup_mw"].sum())
    curt = float(s["curtail_mw"].sum())
    return {
        "backup_mwh": round(backup, 3),
        "curtail_mwh": round(curt, 3),
        "cost_inr": round(backup * costs.backup_inr_per_mwh + curt * costs.curtail_penalty_inr_per_mwh, 0),
        "co2_t": round(backup * costs.emission_factor_t_per_mwh, 3),
        "battery_throughput_mwh": round(float((s["charge_mw"] + s["discharge_mw"]).sum()), 3),
    }
