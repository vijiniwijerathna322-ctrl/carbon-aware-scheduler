"""Forecaster contract and shared time-series validation."""

from collections.abc import Sequence
from typing import Protocol

import numpy as np
import pandas as pd

HORIZONS = tuple(range(1, 49))


class Forecaster(Protocol):
    def fit(self, series: pd.Series, fit_end: pd.Timestamp) -> None: ...

    def predict(self, series: pd.Series, issue_time: pd.Timestamp) -> pd.DataFrame: ...


def validate_series(series: pd.Series) -> None:
    index = series.index
    if not isinstance(index, pd.DatetimeIndex) or str(index.tz) != "UTC":
        raise ValueError("Series must have a UTC DatetimeIndex")
    if index.hasnans or not index.equals(index.floor("h")):
        raise ValueError("Series must contain valid whole hours")
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("Series index must be unique and increasing")
    if len(index) and not index.equals(pd.date_range(index[0], periods=len(index), freq="h")):
        raise ValueError("Series must be regular hourly; retain gaps as NaN")
    if not pd.api.types.is_numeric_dtype(series.dtype) or pd.api.types.is_bool_dtype(series.dtype):
        raise ValueError("Series must be numeric")
    if np.isinf(series.to_numpy(dtype=float, na_value=np.nan)).any():
        raise ValueError("Series must be finite or NaN")


def utc_hour(value: pd.Timestamp) -> pd.Timestamp:
    if pd.isna(value) or value.tz is None or value != value.floor("h"):
        raise ValueError("Time must be a timezone-aware whole hour")
    return value.tz_convert("UTC")


def validate_horizons(horizons: Sequence[int]) -> tuple[int, ...]:
    values = tuple(horizons)
    if (
        not values
        or len(set(values)) != len(values)
        or any(isinstance(h, bool) or not isinstance(h, int) or h < 1 for h in values)
    ):
        raise ValueError("horizons must be distinct positive integers")
    return values
