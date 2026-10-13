"""Explicit small-sample status and nominal coverage diagnostics."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.stats import binomtest  # type: ignore[import-untyped]


@dataclass(frozen=True)
class CoverageStatus:
    n: int
    coverage: float | None
    p_value: float | None
    status: Literal["ok", "alert", "insufficient_data"]


def coverage_status(  # noqa: PLR0913, PLR0917
    y: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    nominal: float = 0.8,
    min_points: int = 100,
    p_threshold: float = 0.01,
) -> CoverageStatus:
    arrays = [np.asarray(values, dtype=float) for values in (y, lower, upper)]
    if any(a.ndim != 1 or np.isinf(a).any() for a in arrays) or len({len(a) for a in arrays}) != 1:
        raise ValueError("Need aligned one-dimensional finite-or-NaN arrays")
    if not 0 < nominal < 1 or not 0 < p_threshold < 1 or min_points < 1:
        raise ValueError("Invalid coverage test configuration")
    actual, lo, hi = arrays
    valid = np.isfinite(actual) & np.isfinite(lo) & np.isfinite(hi)
    if (lo[valid] > hi[valid]).any():
        raise ValueError("Interval lower must not exceed upper")
    n = int(valid.sum())
    successes = int(((lo[valid] <= actual[valid]) & (actual[valid] <= hi[valid])).sum())
    coverage = successes / n if n else None
    if n < min_points:
        return CoverageStatus(n, coverage, None, "insufficient_data")
    p_value = float(binomtest(successes, n, nominal, alternative="two-sided").pvalue)
    return CoverageStatus(n, coverage, p_value, "alert" if p_value < p_threshold else "ok")


def mae_ratio_status(recent_mae: float, baseline_mae: float) -> Literal["ok", "warn", "alert"]:
    if not all(np.isfinite(v) and v >= 0 for v in (recent_mae, baseline_mae)):
        raise ValueError("MAE values must be finite and nonnegative")
    if baseline_mae == 0:
        return "ok" if recent_mae == 0 else "alert"
    ratio = recent_mae / baseline_mae
    if ratio >= 2:  # noqa: PLR2004
        return "alert"
    return "warn" if ratio >= 1.5 else "ok"  # noqa: PLR2004
