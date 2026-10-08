"""Alerts engine: probabilistic threshold alerts merged into time windows."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from terra.config import AlertsCfg
from terra.schema import QCOLS, QUANTILES

_LV = np.array(QUANTILES)


def prob_below(q: np.ndarray, thr: float | np.ndarray) -> np.ndarray:
    """P(X < thr) per row from quantile rows (linear CDF interpolation; tails extrapolated).

    `thr` may be a scalar or one threshold per row.
    """
    thrs = np.broadcast_to(np.asarray(thr, float), (len(q),))
    out = np.empty(len(q))
    for i, row in enumerate(q):
        thr = thrs[i]
        if thr <= row[0]:
            out[i] = 0.025 * (thr / row[0]) if row[0] > 0 else 0.0
        elif thr >= row[-1]:
            out[i] = 0.975 + 0.025 * min(1.0, (thr - row[-1]) / max(row[-1], 1e-6))
        else:
            out[i] = np.interp(thr, row, _LV)
    return np.clip(out, 0, 1)


@dataclass
class Alert:
    id: str
    type: str
    source: str
    start_utc: str
    end_utc: str
    severity: str
    probability: float
    magnitude_mw: float
    message: str
    issue_time_utc: str

    def to_dict(self) -> dict:
        return asdict(self)


def _windows(mask: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        if not m and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def _severity(p: float, frac: float) -> str:
    s = p * (0.5 + frac)
    return "critical" if s >= 0.9 else ("warning" if s >= 0.55 else "info")


def generate_alerts(fc: pd.DataFrame, source: str, capacity: float, cfg: AlertsCfg, issue_time: pd.Timestamp,
                    demand: pd.Series | None = None, trust: pd.Series | None = None) -> list[Alert]:
    """fc: index target_time_utc, columns q05..q95 (MW). Optional demand (MW) and trust (0-100)."""
    q = fc[list(QCOLS)].to_numpy()
    t = fc.index
    alerts: list[Alert] = []
    iso = lambda ts: pd.Timestamp(ts).isoformat()  # noqa: E731

    def add(kind: str, mask: np.ndarray, prob: np.ndarray, mag: np.ndarray, text: str) -> None:
        for a, b in _windows(mask):
            p = float(prob[a:b + 1].max())
            m = float(mag[a:b + 1].max())
            aid = f"{kind}:{source}:{iso(t[a])}"
            alerts.append(Alert(aid, kind, source, iso(t[a] - pd.Timedelta(hours=1)), iso(t[b]),
                                _severity(p, m / capacity), round(p, 3), round(m, 2),
                                text.format(p=int(round(100 * p)), m=m), iso(issue_time)))

    low_thr = cfg.low_generation_frac * capacity
    p_low = prob_below(q, low_thr)
    is_day = fc.get("cal_is_day", pd.Series(1, index=t)).to_numpy() == 1 if source == "solar" else np.ones(len(t), bool)
    add("LOW_GENERATION", (p_low >= cfg.min_probability) & is_day, p_low, low_thr - q[:, 2],
        f"{source.title()} likely below {low_thr:.0f} MW ({{p}}% chance)")
    high_thr = cfg.high_generation_frac * capacity
    p_high = 1 - prob_below(q, high_thr)
    add("HIGH_GENERATION", p_high >= cfg.min_probability, p_high, q[:, 2] - high_thr,
        f"{source.title()} likely above {high_thr:.0f} MW — curtailment risk ({{p}}% chance)")
    ramp = np.abs(np.diff(q[:, 2], prepend=q[0, 2]))
    add("RAMP", ramp >= cfg.ramp_mw_per_h, np.minimum(1, ramp / (2 * cfg.ramp_mw_per_h)), ramp,
        "Fast change of {m:.0f} MW within an hour")
    if demand is not None:                                             # use with source="hybrid"
        d = demand.reindex(t).to_numpy()
        p_def = prob_below(q, d)                                       # P(supply < demand)
        add("DEFICIT_VS_DEMAND", p_def >= cfg.min_probability, p_def, d - q[:, 2],
            "Supply may fall {m:.0f} MW short of demand ({p}% chance)")
    if trust is not None:
        tr = trust.reindex(t).to_numpy()
        add("LOW_CONFIDENCE", tr < cfg.low_trust_score, 1 - tr / 100, (100 - tr) / 100 * capacity * 0.1,
            "Forecast confidence is low")
    return alerts


def alert_skill(alert_windows: list[Alert], actual: pd.Series, kind: str, thr: float) -> dict[str, float]:
    """Precision/recall of LOW/HIGH alerts against actual threshold crossings (hourly)."""
    flagged = pd.Series(False, index=actual.index)
    for a in alert_windows:
        if a.type == kind:
            flagged.loc[pd.Timestamp(a.start_utc) + pd.Timedelta(hours=1): pd.Timestamp(a.end_utc)] = True
    event = actual < thr if kind == "LOW_GENERATION" else actual > thr
    tp = float((flagged & event).sum())
    return {"precision": tp / max(flagged.sum(), 1), "recall": tp / max(event.sum(), 1)}
