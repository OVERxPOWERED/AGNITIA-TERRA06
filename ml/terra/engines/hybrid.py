"""H1 Hybrid engine: combine solar + wind forecasts with a Gaussian copula; complementarity stats.

Never add quantiles of two variables (that over-states uncertainty). Instead:
1. Fit the correlation rho of the two sources' PIT values (probability integral transform) on validation.
2. Sample correlated uniforms, map through each source's quantile function, add, take quantiles.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from terra.schema import QCOLS, QUANTILES

_LEVELS = np.array(QUANTILES)


def _quantile_fn(qrow: np.ndarray, capacity: float):
    """Piecewise-linear quantile function through (0,0),(0.05,q05)...(0.95,q95),(1,cap-ish)."""
    lo = max(0.0, qrow[0] - (qrow[1] - qrow[0]))
    hi = min(capacity, qrow[-1] + (qrow[-1] - qrow[-2]))
    levels = np.concatenate([[0.0], _LEVELS, [1.0]])
    values = np.concatenate([[lo], qrow, [hi]])
    return levels, np.maximum.accumulate(values)


def pit(y: np.ndarray, q: np.ndarray, capacity: float) -> np.ndarray:
    """Probability integral transform u = F(y) for each row (y actual, q rows of quantiles)."""
    u = np.empty(len(y))
    for i in range(len(y)):
        lv, vals = _quantile_fn(q[i], capacity)
        u[i] = np.interp(y[i], vals, lv) if vals[-1] > vals[0] else 0.5
    return np.clip(u, 1e-3, 1 - 1e-3)


def fit_copula_rho(u_solar: np.ndarray, u_wind: np.ndarray, is_day: np.ndarray) -> dict[int, float]:
    """Gaussian-copula correlation separately for day and night hours."""
    out = {}
    for d in (0, 1):
        sel = is_day == d
        if sel.sum() > 30:
            z1, z2 = norm.ppf(u_solar[sel]), norm.ppf(u_wind[sel])
            r = np.corrcoef(z1, z2)[0, 1]          # NaN if one side is constant (e.g. solar at night)
            out[d] = float(np.clip(np.nan_to_num(r, nan=0.0), -0.95, 0.95))
        else:
            out[d] = 0.0
    return out


def combine(q_solar: np.ndarray, q_wind: np.ndarray, cap_solar: float, cap_wind: float,
            rho: np.ndarray, n_samples: int = 1000, seed: int = 0) -> np.ndarray:
    """Return combined quantiles (N x 5) for each hour; rho is per-row correlation."""
    rng = np.random.default_rng(seed)
    out = np.empty((len(q_solar), len(QUANTILES)))
    z1 = rng.standard_normal(n_samples)
    e = rng.standard_normal(n_samples)
    for i in range(len(q_solar)):
        z2 = rho[i] * z1 + np.sqrt(1 - rho[i] ** 2) * e
        u1, u2 = norm.cdf(z1), norm.cdf(z2)
        ls, vs = _quantile_fn(q_solar[i], cap_solar)
        lw, vw = _quantile_fn(q_wind[i], cap_wind)
        total = np.interp(u1, ls, vs) + np.interp(u2, lw, vw)
        out[i] = np.quantile(total, QUANTILES)
    return out


def hybrid_forecast(solar_q: pd.DataFrame, wind_q: pd.DataFrame, is_day: np.ndarray,
                    rho_by_day: dict[int, float], cap_solar: float, cap_wind: float) -> pd.DataFrame:
    rho = np.array([rho_by_day.get(int(d), 0.0) for d in is_day])
    q = combine(solar_q[list(QCOLS)].to_numpy(), wind_q[list(QCOLS)].to_numpy(), cap_solar, cap_wind, rho)
    return pd.DataFrame(q, index=solar_q.index, columns=list(QCOLS))


def complementarity(solar: pd.Series, wind: pd.Series) -> dict[str, float]:
    """How much the two sources smooth each other (computed on actual or P50 series)."""
    total = solar + wind
    cv = lambda s: float(s.std() / s.mean()) if s.mean() > 0 else float("nan")  # noqa: E731
    solar_dip = solar < 0.2 * solar.max()
    covered = (wind > 0.3 * wind.max()) & solar_dip
    return {
        "pearson": float(solar.corr(wind)),
        "cv_solar": cv(solar), "cv_wind": cv(wind), "cv_combined": cv(total),
        "smoothing_pct": 100 * (1 - cv(total) / min(cv(solar), cv(wind))) if min(cv(solar), cv(wind)) > 0 else 0.0,
        "hours_wind_covers_solar_dip_pct": 100 * float(covered.sum() / max(solar_dip.sum(), 1)),
    }
