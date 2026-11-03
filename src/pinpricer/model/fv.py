"""Digital pricing on an averaged settlement index.

Every contract here pays 1 if the settlement average Ā_T is above a strike K. The settlement
is the mean of the 60 one-second index prints before T, so it is an Asian digital: with the
window still ahead, Var(ln Ā_T) = σ²(τ − 0.658·w) for 60 discrete prints over w = 60 s.
Drift is zero (BRTI is built as a martingale; the −V/2 Itô term is under 0.01¢ at these tenors).
"""

from __future__ import annotations

import numpy as np
from scipy import stats

AVG_DISCOUNT = 0.658  # (n+1)(2n+1)/(6n²) shortfall for n = 60 prints, as a fraction of w


def averaged_variance(var_to_expiry: np.ndarray, var_last_window: np.ndarray, averaging: bool = True):
    """Total log-variance of the settlement average seen from τ ≥ w before expiry."""
    if not averaging:
        return var_to_expiry
    return np.maximum(var_to_expiry - AVG_DISCOUNT * var_last_window, 1e-12)


def prob_above(spot, strike, var, nu: float | np.ndarray | None = None) -> np.ndarray:
    """P(ln Ā_T > ln K) for a zero-drift, unit-variance-scaled normal or Student-t return."""
    z = np.log(np.asarray(strike) / np.asarray(spot)) / np.sqrt(var)
    if nu is None:
        return stats.norm.sf(z)
    nu = np.asarray(nu, dtype=float)
    return stats.t.sf(z / np.sqrt((nu - 2) / nu), nu)


def fit_student_t_nu(z: np.ndarray, grid: np.ndarray | None = None) -> float:
    """MLE of ν for a unit-variance Student-t fitted to standardized returns z."""
    grid = np.arange(2.2, 30.01, 0.1) if grid is None else grid
    z = z[np.isfinite(z)]
    ll = [stats.t.logpdf(z / np.sqrt((v - 2) / v), v).sum() - len(z) * 0.5 * np.log((v - 2) / v)
          for v in grid]
    return float(grid[int(np.argmax(ll))])
