"""Reference-quantile PSI and two-sample KS diagnostics."""

from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray
from scipy.stats import ks_2samp  # type: ignore[import-untyped]

Status = Literal["ok", "warn", "alert", "insufficient_data"]


def finite_sample(values: NDArray[np.float64]) -> NDArray[np.float64]:
    sample = np.asarray(values, dtype=float)
    if sample.ndim != 1 or np.isinf(sample).any():
        raise ValueError("Samples must be one-dimensional, finite or NaN")
    sample = sample[np.isfinite(sample)]
    if not len(sample):
        raise ValueError("Need at least one finite observation")
    return cast(NDArray[np.float64], sample)


def psi(
    reference: NDArray[np.float64],
    current: NDArray[np.float64],
    bins: int = 10,
    eps: float = 1e-4,
) -> float:
    if isinstance(bins, bool) or not isinstance(bins, int) or bins < 2:  # noqa: PLR2004
        raise ValueError("bins must be an integer >= 2")
    if not np.isfinite(eps) or not 0 < eps < 1:
        raise ValueError("eps must lie in (0,1)")
    ref, cur = finite_sample(reference), finite_sample(current)
    quantiles = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(quantiles) == 1:
        center = quantiles[0]
        edges = np.unique([-np.inf, center, np.nextafter(center, np.inf), np.inf])
    else:
        interior = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)[1:-1]))
        if len(quantiles) == 2:  # noqa: PLR2004
            interior = np.array([quantiles[0] / 2 + quantiles[1] / 2])
        edges = np.r_[-np.inf, interior, np.inf]
    ref_p = np.maximum(np.histogram(ref, edges)[0] / len(ref), eps)
    cur_p = np.maximum(np.histogram(cur, edges)[0] / len(cur), eps)
    ref_p, cur_p = ref_p / ref_p.sum(), cur_p / cur_p.sum()
    return float(np.sum((cur_p - ref_p) * np.log(cur_p / ref_p)))


def ks_drift(reference: NDArray[np.float64], current: NDArray[np.float64]) -> tuple[float, float]:
    result = ks_2samp(finite_sample(reference), finite_sample(current))
    return float(result.statistic), float(result.pvalue)


def classify_psi(value: float) -> Literal["ok", "warn", "alert"]:
    if not np.isfinite(value) or value < 0:
        raise ValueError("PSI must be finite and nonnegative")
    if value >= 0.25:  # noqa: PLR2004
        return "alert"
    return "warn" if value >= 0.1 else "ok"  # noqa: PLR2004
