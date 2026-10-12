"""Position-wise forecast metrics with explicit missing-observation handling."""

import numpy as np
import numpy.typing as npt

ArrayLike = npt.ArrayLike
FloatArray = npt.NDArray[np.float64]


def _pairs(*values: ArrayLike) -> list[FloatArray]:
    arrays = [np.asarray(value, dtype=float) for value in values]
    if any(a.ndim != 1 or a.shape != arrays[0].shape for a in arrays):
        raise ValueError("Metric inputs must have the same one-dimensional shape")
    if any(np.isinf(a).any() for a in arrays):
        raise ValueError("Metric observations must be finite or NaN")
    mask = np.logical_and.reduce([~np.isnan(a) for a in arrays])
    return [a[mask] for a in arrays]


def _mean(values: FloatArray) -> float:
    return float(values.mean()) if len(values) else float("nan")


def _alpha(alpha: float) -> None:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")


def _ordered(lower: FloatArray, upper: FloatArray) -> None:
    if (lower > upper).any():
        raise ValueError("Interval bounds must be ordered")


def mae(y: ArrayLike, pred: ArrayLike) -> float:
    actual, predicted = _pairs(y, pred)
    return _mean(np.abs(actual - predicted))


def pinball_loss(y: ArrayLike, q_pred: ArrayLike, alpha: float) -> float:
    _alpha(alpha)
    actual, predicted = _pairs(y, q_pred)
    error = actual - predicted
    return _mean(np.maximum(alpha * error, (alpha - 1) * error))


def interval_coverage(y: ArrayLike, lower: ArrayLike, upper: ArrayLike) -> float:
    actual, lo, hi = _pairs(y, lower, upper)
    _ordered(lo, hi)
    return _mean(((lo <= actual) & (actual <= hi)).astype(float))


def mean_interval_width(lower: ArrayLike, upper: ArrayLike) -> float:
    lo, hi = _pairs(lower, upper)
    _ordered(lo, hi)
    return _mean(hi - lo)


def winkler_score(y: ArrayLike, lower: ArrayLike, upper: ArrayLike, alpha: float) -> float:
    _alpha(alpha)
    actual, lo, hi = _pairs(y, lower, upper)
    _ordered(lo, hi)
    return _mean(hi - lo + 2 / alpha * (np.maximum(lo - actual, 0) + np.maximum(actual - hi, 0)))
