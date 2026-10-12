"""Finite-sample, horizon-bucket split-conformal quantile corrections."""

import logging
import math
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from carbon_scheduler.models.evaluate import BUCKETS

logger = logging.getLogger(__name__)
FloatArray = npt.NDArray[np.float64]


class SplitConformalCQR:
    def __init__(
        self,
        alpha: float = 0.2,
        buckets: Sequence[tuple[int, int]] = BUCKETS,
        min_points: int = 30,
    ) -> None:
        if not 0 < alpha < 1:
            raise ValueError("alpha must lie in (0, 1)")
        covered = [h for lo, hi in buckets for h in range(lo, hi + 1)]
        if sorted(covered) != list(range(1, 49)) or min_points < 1:
            raise ValueError(
                "Buckets must partition horizons 1..48 and min_points must be positive"
            )
        self.alpha = alpha
        self.buckets = tuple(buckets)
        self.min_points = min_points
        self.corrections_: dict[tuple[int, int], float] = {}
        self.pooled_correction_: float | None = None

    def _arrays(self, *values: npt.ArrayLike) -> list[FloatArray]:
        arrays = [np.asarray(value, dtype=float) for value in values]
        if any(a.ndim != 1 or a.shape != arrays[0].shape for a in arrays):
            raise ValueError("Inputs must share one-dimensional shape")
        return arrays

    def _horizons(self, horizon: FloatArray) -> None:
        if not np.isin(horizon, range(1, 49)).all():
            raise ValueError("horizon must contain integers in 1..48")

    def _correction(self, scores: FloatArray) -> float:
        # The kth order statistic is the empirical inverse-CDF quantile at k/n;
        # interpolated/default or 'higher' quantiles use a different rank.
        rank = min(len(scores), math.ceil((len(scores) + 1) * (1 - self.alpha)))
        return float(np.partition(scores, rank - 1)[rank - 1])

    def calibrate(
        self,
        lower: npt.ArrayLike,
        upper: npt.ArrayLike,
        y: npt.ArrayLike,
        horizon: npt.ArrayLike,
    ) -> "SplitConformalCQR":
        lo, hi, actual, hs = self._arrays(lower, upper, y, horizon)
        finite = np.isfinite(lo) & np.isfinite(hi) & np.isfinite(actual) & np.isfinite(hs)
        lo, hi, actual, hs = [a[finite] for a in (lo, hi, actual, hs)]
        if not len(actual):
            raise ValueError("Need finite calibration observations")
        self._horizons(hs)
        if (lo > hi).any():
            raise ValueError("Calibration intervals must be ordered")
        if np.ptp(actual) == 0:
            logger.warning("Calibration target is constant; corrections use measured scores")
        scores = np.maximum(lo - actual, actual - hi)
        pooled = self._correction(scores)
        corrections = {}
        for bucket in self.buckets:
            lo_h, hi_h = bucket
            selected = scores[(hs >= lo_h) & (hs <= hi_h)]
            if len(selected) < self.min_points:
                logger.warning(
                    "Bucket %s has %d points; using pooled correction", bucket, len(selected)
                )
                corrections[bucket] = pooled
            else:
                corrections[bucket] = self._correction(selected)
        self.pooled_correction_ = pooled
        self.corrections_ = corrections
        return self

    def adjust(
        self,
        lower: npt.ArrayLike,
        upper: npt.ArrayLike,
        horizon: npt.ArrayLike,
    ) -> tuple[FloatArray, FloatArray]:
        if self.pooled_correction_ is None:
            raise RuntimeError("Call calibrate before adjust")
        lo, hi, hs = self._arrays(lower, upper, horizon)
        self._horizons(hs)
        if (lo > hi).any() or np.isinf(lo).any() or np.isinf(hi).any():
            raise ValueError("Prediction intervals must be ordered and finite or NaN")
        correction = np.empty(len(hs))
        for (start, end), value in self.corrections_.items():
            correction[(hs >= start) & (hs <= end)] = value
        adjusted_lo, adjusted_hi = lo - correction, hi + correction
        crossed = adjusted_lo > adjusted_hi
        midpoint = (adjusted_lo + adjusted_hi) / 2
        return np.where(crossed, midpoint, adjusted_lo), np.where(crossed, midpoint, adjusted_hi)
