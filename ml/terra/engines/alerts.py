"""Alerts engine: probabilistic threshold alerts merged into time windows."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from terra.config import AlertsCfg
from terra.schema import QCOLS, QUANTILES

if TYPE_CHECKING:
    from terra.config import TerraConfig

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


def alert_thresholds(
    ds: pd.DataFrame,
    cfg: TerraConfig | AlertsCfg | None = None,
    *,
    low_quantile: float | dict[str, float] | None = None,
    high_quantile: float | None = None,
    ramp_quantile: float | None = None,
) -> dict[str, dict[str, float]]:
    """Compute data-driven alert thresholds per source strictly from the training split (leak-free).

    Returns per source {"low_mw", "high_mw", "ramp_mw_per_h"}.
    - low_mw: low_quantile of generation (for solar: daylight hours only, cal_is_day == 1 / zenith < 90)
    - high_mw: high_quantile of generation (for solar: daylight only)
    - ramp_mw_per_h: ramp_quantile of |hour-to-hour change of generation| over the training split
    - hybrid: uses solar + wind generation sum
    """
    train_ds = ds
    # Slice training split if cfg has split bounds or ds has split column
    if cfg is not None and hasattr(cfg, "splits") and hasattr(cfg.splits, "bounds"):
        low_q = low_quantile if low_quantile is not None else cfg.alerts.low_quantile
        high_q = high_quantile if high_quantile is not None else cfg.alerts.high_quantile
        ramp_q = ramp_quantile if ramp_quantile is not None else cfg.alerts.ramp_quantile
        if "split" in ds.columns:
            train_ds = ds[ds["split"] == "train"]
        elif isinstance(ds.index, pd.DatetimeIndex):
            bounds = cfg.splits.bounds()["train"]
            train_ds = ds.loc[bounds[0]:bounds[1]]
    else:
        if isinstance(cfg, AlertsCfg):
            low_q = low_quantile if low_quantile is not None else cfg.low_quantile
            high_q = high_quantile if high_quantile is not None else cfg.high_quantile
            ramp_q = ramp_quantile if ramp_quantile is not None else cfg.ramp_quantile
        else:
            low_q = low_quantile if low_quantile is not None else 0.10
            high_q = high_quantile if high_quantile is not None else 0.90
            ramp_q = ramp_quantile if ramp_quantile is not None else 0.95
        if "split" in ds.columns:
            train_ds = ds[ds["split"] == "train"]

    def _source_low_q(src: str) -> float:
        if isinstance(low_q, dict):
            return float(low_q.get(src, 0.10))
        return float(low_q)

    low_q_solar = _source_low_q("solar")
    low_q_wind = _source_low_q("wind")
    low_q_hybrid = _source_low_q("hybrid")

    s_col = "solar_mw" if "solar_mw" in train_ds.columns else "solar"
    w_col = "wind_mw" if "wind_mw" in train_ds.columns else "wind"
    sol = train_ds[s_col].astype(float)
    win = train_ds[w_col].astype(float)
    if "hybrid_mw" in train_ds.columns:
        hyb = train_ds["hybrid_mw"].astype(float)
    elif "hybrid" in train_ds.columns:
        hyb = train_ds["hybrid"].astype(float)
    else:
        hyb = sol + win

    if "cal_is_day" in train_ds.columns:
        is_day = train_ds["cal_is_day"].to_numpy() == 1
    elif "zenith" in train_ds.columns:
        is_day = train_ds["zenith"].to_numpy() < 90
    else:
        is_day = np.ones(len(train_ds), dtype=bool)

    sol_day = sol[is_day]

    return {
        "solar": {
            "low_mw": round(float(sol_day.quantile(low_q_solar)), 3),
            "high_mw": round(float(sol_day.quantile(high_q)), 3),
            "ramp_mw_per_h": round(float(sol.diff().abs().dropna().quantile(ramp_q)), 3),
        },
        "wind": {
            "low_mw": round(float(win.quantile(low_q_wind)), 3),
            "high_mw": round(float(win.quantile(high_q)), 3),
            "ramp_mw_per_h": round(float(win.diff().abs().dropna().quantile(ramp_q)), 3),
        },
        "hybrid": {
            "low_mw": round(float(hyb.quantile(low_q_hybrid)), 3),
            "high_mw": round(float(hyb.quantile(high_q)), 3),
            "ramp_mw_per_h": round(float(hyb.diff().abs().dropna().quantile(ramp_q)), 3),
        },
    }


def generate_alerts(fc: pd.DataFrame, source: str, capacity: float, cfg: AlertsCfg, issue_time: pd.Timestamp,
                    demand: pd.Series | None = None, trust: pd.Series | None = None,
                    thresholds: dict[str, float] | dict[str, dict[str, float]] | None = None) -> list[Alert]:
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
            extra: dict[str, float] = {}
            if kind == "LOW_CONFIDENCE" and trust is not None:
                extra["score"] = float(tr[a:b + 1].min())
                extra["threshold"] = float(cfg.low_trust_score)
            alerts.append(Alert(aid, kind, source, iso(t[a] - pd.Timedelta(hours=1)), iso(t[b]),
                                _severity(p, m / capacity), round(p, 3), round(m, 2),
                                text.format(p=int(round(100 * p)), m=m, **extra), iso(issue_time)))

    low_thr = cfg.low_generation_frac * capacity
    high_thr = cfg.high_generation_frac * capacity
    ramp_thr = cfg.ramp_mw_per_h

    if thresholds is not None:
        th = thresholds.get(source, thresholds) if isinstance(thresholds, dict) else {}
        if isinstance(th, dict):
            if "low_mw" in th:
                low_thr = float(th["low_mw"])
            if "high_mw" in th:
                high_thr = float(th["high_mw"])
            if "ramp_mw_per_h" in th:
                ramp_thr = float(th["ramp_mw_per_h"])

    p_low = prob_below(q, low_thr)
    is_day = fc.get("cal_is_day", pd.Series(1, index=t)).to_numpy() == 1 if source == "solar" else np.ones(len(t), bool)
    add("LOW_GENERATION", (p_low >= cfg.min_probability) & is_day, p_low, low_thr - q[:, 2],
        f"{source.title()} likely below {low_thr:.1f} MW ({{p}}% chance)")
    p_high = 1 - prob_below(q, high_thr)
    add("HIGH_GENERATION", p_high >= cfg.min_probability, p_high, q[:, 2] - high_thr,
        f"{source.title()} likely above {high_thr:.1f} MW — curtailment risk ({{p}}% chance)")
    ramp = np.abs(np.diff(q[:, 2], prepend=q[0, 2]))
    add("RAMP", ramp >= ramp_thr, np.minimum(1, ramp / (2 * ramp_thr)), ramp,
        f"Fast change of {{m:.1f}} MW within an hour (threshold {ramp_thr:.1f} MW/h, {{p}}% chance)")
    if demand is not None:                                             # use with source="hybrid"
        d = demand.reindex(t).to_numpy()
        p_def = prob_below(q, d)                                       # P(supply < demand)
        add("DEFICIT_VS_DEMAND", p_def >= cfg.min_probability, p_def, d - q[:, 2],
            "Supply may fall {m:.0f} MW short of demand ({p}% chance)")
    if trust is not None:
        tr = trust.reindex(t).to_numpy()
        add("LOW_CONFIDENCE", tr < cfg.low_trust_score, 1 - tr / 100, (100 - tr) / 100 * capacity * 0.1,
            "Forecast confidence is low (trust score {score:.0f} < {threshold:.0f})")
    return alerts


def alert_skill(alert_windows: list[Alert] | pd.Series, actual: pd.Series, kind: str, thr: float) -> dict[str, float | int]:
    """Precision/recall of LOW/HIGH alerts against actual threshold crossings (hourly)."""
    if isinstance(alert_windows, pd.Series):
        flagged = alert_windows.reindex(actual.index).fillna(False).astype(bool)
    else:
        flagged = pd.Series(False, index=actual.index)
        for a in alert_windows:
            if a.type == kind:
                flagged.loc[pd.Timestamp(a.start_utc) + pd.Timedelta(hours=1): pd.Timestamp(a.end_utc)] = True
    event = actual < thr if kind == "LOW_GENERATION" else actual > thr
    tp = float((flagged & event).sum())
    alert_hours = int(flagged.sum())
    event_hours = int(event.sum())
    return {
        "precision": float(tp / max(alert_hours, 1)),
        "recall": float(tp / max(event_hours, 1)),
        "alert_hours": alert_hours,
        "event_hours": event_hours,
    }


def evaluate_alert_quality(
    preds_by_source: dict[str, pd.DataFrame],
    cfg: TerraConfig,
    thresholds: dict[str, dict[str, float]],
) -> dict[str, dict[str, dict[str, float | int]]]:
    """Evaluate precision and recall of alerts on the test split with deduplicated overlapping hours.

    Uses daily 00:00 UTC issue times and the 48 h horizon.
    Deduplicates overlapping target hours by selecting the alert from the most recent issue time.
    For solar, only daylight hours count.
    """
    res: dict[str, dict[str, dict[str, float | int]]] = {}
    for source in ("solar", "wind", "hybrid"):
        df = preds_by_source[source]
        p = df.copy()
        if "model" in p.columns:
            p = p[p["model"] == "ensemble"]
        if "split" in p.columns:
            p = p[p["split"] == "test"]
        p = p[(p["issue_time_utc"].dt.hour == 0) & (p["lead_h"] <= 48)]

        cap = cfg.capacity_mw(source)
        th = thresholds.get(source, {})
        low_thr = th.get("low_mw", cfg.alerts.low_generation_frac * cap)
        high_thr = th.get("high_mw", cfg.alerts.high_generation_frac * cap)

        records = []
        for it, g in p.groupby("issue_time_utc"):
            fc = g.set_index("target_time_utc")
            is_day = fc["cal_is_day"].to_numpy() == 1 if "cal_is_day" in fc.columns else np.ones(len(fc), bool)
            alerts = generate_alerts(fc, source, cap, cfg.alerts, it, thresholds=th)

            flag_low = pd.Series(False, index=fc.index)
            flag_high = pd.Series(False, index=fc.index)
            for a in alerts:
                if a.type == "LOW_GENERATION":
                    flag_low.loc[pd.Timestamp(a.start_utc) + pd.Timedelta(hours=1): pd.Timestamp(a.end_utc)] = True
                elif a.type == "HIGH_GENERATION":
                    flag_high.loc[pd.Timestamp(a.start_utc) + pd.Timedelta(hours=1): pd.Timestamp(a.end_utc)] = True

            for idx_i, tgt in enumerate(fc.index):
                records.append({
                    "issue_time_utc": it,
                    "target_time_utc": tgt,
                    "flag_low": bool(flag_low.iloc[idx_i]),
                    "flag_high": bool(flag_high.iloc[idx_i]),
                    "y": float(fc["y"].iloc[idx_i]) if "y" in fc.columns else np.nan,
                    "cal_is_day": bool(is_day[idx_i]),
                })

        rec_df = pd.DataFrame(records)
        deduped = rec_df.sort_values("issue_time_utc").groupby("target_time_utc").last()

        eval_df = deduped[deduped["cal_is_day"]] if source == "solar" else deduped
        low_skill = alert_skill(eval_df["flag_low"], eval_df["y"], "LOW_GENERATION", low_thr)
        high_skill = alert_skill(eval_df["flag_high"], eval_df["y"], "HIGH_GENERATION", high_thr)
        res[source] = {"low": low_skill, "high": high_skill}

    return res
