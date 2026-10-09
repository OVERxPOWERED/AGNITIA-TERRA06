"""Deviation watch: compare the latest forecast with the schedule the operator already submitted.

Under the DSM regulations the plant is charged for deviating from its submitted schedule beyond a tolerance band
(config/dsm.yaml: hybrid 5% of available capacity). When an updated forecast moves outside that band for at least
MIN_BLOCKS consecutive 15-minute blocks, the operator should revise the schedule with the load despatch centre
before those blocks start. Each such run of blocks becomes one critical DEVIATION_RISK alert.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from terra.engines.alerts import Alert
from terra.engines.dsm import DsmProfile, deviation_charges

MIN_BLOCKS = 4                    # one hour


def deviation_risk_alerts(expected: pd.Series, committed: pd.Series, avc_mw: float, issue: pd.Timestamp,
                          prof: DsmProfile | None = None, source: str = "hybrid", plant: str = "") -> list[Alert]:
    """expected / committed: MW per 15-minute block, indexed by block end (UTC)."""
    prof = prof or DsmProfile.load()
    idx = expected.index.intersection(committed.index)
    idx = idx[idx > issue]
    if len(idx) < MIN_BLOCKS:
        return []
    e, c = expected.reindex(idx).to_numpy(), committed.reindex(idx).to_numpy()
    ch = deviation_charges(c, e, avc_mw, source, prof)
    tol = prof.tolerance_pct[source]
    over = (ch["beyond_tolerance_pct"] > 0).to_numpy()
    out = []
    i = 0
    while i < len(idx):
        if not over[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(idx) and over[j + 1] and idx[j + 1] - idx[j] == pd.Timedelta(minutes=15):
            j += 1
        if j - i + 1 >= MIN_BLOCKS:
            seg = slice(i, j + 1)
            dev = ch["deviation_pct"].to_numpy()[seg]
            k = int(np.argmax(np.abs(dev)))
            direction = "above" if dev[k] > 0 else "below"
            start, end = idx[i] - pd.Timedelta(minutes=15), idx[j]
            ist = lambda t: t.tz_convert("Asia/Kolkata").strftime("%d %b %H:%M")  # noqa: E731
            charge = float(ch["charge_inr"].to_numpy()[seg].sum())
            aid = hashlib.sha1(f"DEV|{source}|{start}|{issue.normalize()}".encode()).hexdigest()[:12]
            out.append(Alert(
                id=aid, type="DEVIATION_RISK", source=source,
                start_utc=start.strftime("%Y-%m-%dT%H:%M:%SZ"), end_utc=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                severity="critical", probability=1.0, magnitude_mw=float(abs(e[seg] - c[seg]).max()),
                message=(f"{plant + ': ' if plant else ''}forecast is {abs(dev[k]):.0f}% of capacity {direction} "
                         f"the submitted schedule (band ±{tol:g}%) from {ist(start)} to {ist(end)} IST. "
                         "Revise the schedule with your load despatch centre (SLDC/RLDC) before then to avoid "
                         f"deviation charges (about Rs {charge:,.0f} at illustrative rates)."),
                issue_time_utc=issue.strftime("%Y-%m-%dT%H:%M:%SZ")))
        i = j + 1
    return out
