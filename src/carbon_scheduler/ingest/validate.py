"""Retrospective hourly cleaning and explicit completeness diagnostics."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from carbon_scheduler.ingest.transform import REGION_COLUMNS


@dataclass(frozen=True)
class QualityReport:
    n_rows: int
    n_negative_demand: int
    n_spikes: int
    n_interpolated: int
    n_remaining_gaps: int
    gap_fraction: float
    n_remaining_missing_cells: int = 0
    missing_by_column: dict[str, int] = field(default_factory=dict)
    first_observed_by_column: dict[str, str | None] = field(default_factory=dict)
    last_observed_by_column: dict[str, str | None] = field(default_factory=dict)
    interior_missing_by_column: dict[str, int] = field(default_factory=dict)
    n_duplicates: int = 0


def _check_frame(df: pd.DataFrame) -> None:
    index = df.index
    if not isinstance(index, pd.DatetimeIndex) or str(index.tz) != "UTC":
        raise ValueError("frame index must be a UTC DatetimeIndex")
    if index.hasnans or not index.equals(index.floor("h")):
        raise ValueError("frame index must contain valid whole UTC hours")
    if len(index) and not index.equals(pd.date_range(index[0], periods=len(index), freq="h")):
        raise ValueError("frame index must be unique, increasing and regular hourly")
    if not df.columns.is_unique or not all(isinstance(c, str) for c in df.columns):
        raise ValueError("frame columns must be unique strings")
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in df.dtypes):
        raise ValueError("frame values must be numeric")
    if np.isinf(df.to_numpy(dtype=float)).any():
        raise ValueError("frame contains nonfinite infinite values")


def _spikes(series: pd.Series, threshold: float) -> pd.Series:
    rolling = series.rolling(168, center=True, min_periods=1)
    median = rolling.median()
    # MAD is calculated around each window's own median, not a rolling median
    # of residuals from different windows.
    mad = rolling.apply(
        lambda window: float(np.nanmedian(np.abs(window - np.nanmedian(window)))), raw=True
    )
    deviation = (series - median).abs()
    return (0.6744897501960817 * deviation > threshold * mad) & series.notna()


def _fill_short_runs(series: pd.Series, max_gap: int) -> pd.Series:
    missing = series.isna()
    groups = missing.ne(missing.shift()).cumsum()
    lengths = missing.groupby(groups).transform("sum")
    eligible = missing & lengths.le(max_gap)
    interpolated = series.interpolate(method="linear", limit_area="inside")
    return series.mask(eligible, interpolated)


def validate_and_clean(
    df: pd.DataFrame, *, spike_z: float = 8.0, max_gap_hours: int = 3
) -> tuple[pd.DataFrame, QualityReport]:
    """Clean a copy; G2 measures four core series, not fuel-mix accuracy.

    Centered windows and interpolation use future observations. Forecast/backtest
    callers must not interpret this retrospective cleaning as issue-time data.
    Infinite values are rejected, rather than silently changing quality counts.
    """
    _check_frame(df)
    if not np.isfinite(spike_z) or spike_z <= 0 or max_gap_hours < 0:
        raise ValueError("spike_z must be positive finite and max_gap_hours nonnegative")
    cleaned = df.copy(deep=True)
    negative = 0
    if "demand_mwh" in cleaned:
        invalid = cleaned["demand_mwh"].le(0)
        negative = int(invalid.sum())
        cleaned.loc[invalid, "demand_mwh"] = np.nan
    spikes = 0
    for column in ("demand_mwh", "net_generation_mwh"):
        if column in cleaned:
            invalid = _spikes(cleaned[column], spike_z)
            spikes += int(invalid.sum())
            cleaned.loc[invalid, column] = np.nan
    before = int(cleaned.isna().sum().sum())
    for label in cleaned:
        cleaned[label] = _fill_short_runs(cleaned[label], max_gap_hours)
    missing = cleaned.isna()
    remaining_cells = int(missing.sum().sum())
    core_missing = cleaned.reindex(columns=list(REGION_COLUMNS.values())).isna().any(axis=1)
    gaps = int(core_missing.sum())
    counts = {str(c): int(missing[c].sum()) for c in cleaned}
    for column in REGION_COLUMNS.values():
        counts.setdefault(column, len(cleaned))
    first: dict[str, str | None] = {}
    last: dict[str, str | None] = {}
    interior: dict[str, int] = {}
    for column in counts:
        series = cleaned[column] if column in cleaned else pd.Series(np.nan, index=cleaned.index)
        observed = cleaned.index[series.notna()]
        start = observed[0] if len(observed) else None
        end = observed[-1] if len(observed) else None
        first[column] = start.isoformat() if start is not None else None
        last[column] = end.isoformat() if end is not None else None
        interior[column] = int(series.loc[start:end].isna().sum()) if start is not None else 0
    return cleaned, QualityReport(
        n_rows=len(cleaned),
        n_negative_demand=negative,
        n_spikes=spikes,
        n_interpolated=before - remaining_cells,
        n_remaining_gaps=gaps,
        gap_fraction=gaps / len(cleaned) if len(cleaned) else 0.0,
        n_remaining_missing_cells=sum(counts.values()),
        missing_by_column=counts,
        first_observed_by_column=first,
        last_observed_by_column=last,
        interior_missing_by_column=interior,
    )
