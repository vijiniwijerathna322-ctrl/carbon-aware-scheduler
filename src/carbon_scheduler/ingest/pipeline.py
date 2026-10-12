"""Incremental ingestion with explicit interval coverage and quality diagnostics."""

import json
from collections.abc import Iterator
from dataclasses import asdict, replace
from typing import Literal

import pandas as pd

from carbon_scheduler.config import Settings
from carbon_scheduler.ingest.eia_client import EiaClient
from carbon_scheduler.ingest.fetchers import PERIOD_FORMAT, fetch_fuel_type_data, fetch_region_data
from carbon_scheduler.ingest.store import hourly_path, read_hourly, write_hourly
from carbon_scheduler.ingest.transform import to_hourly_frame
from carbon_scheduler.ingest.validate import QualityReport, validate_and_clean
from carbon_scheduler.regions import load_regions

G2_MAX_GAP_FRACTION = 0.02


def _hour(value: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    timestamp = (
        timestamp.tz_localize("UTC") if timestamp.tz is None else timestamp.tz_convert("UTC")
    )
    if pd.isna(timestamp) or timestamp != timestamp.floor("h"):
        raise ValueError("Bounds must be valid whole UTC hours")
    return timestamp


def _year_windows(start: pd.Timestamp, end: pd.Timestamp) -> Iterator[tuple[str, str]]:
    """Bound upstream query size using adjacent inclusive UTC calendar years."""
    current = start
    while current <= end:
        next_year = pd.Timestamp(year=current.year + 1, month=1, day=1, tz="UTC")
        upper = min(end, next_year - pd.Timedelta(hours=1))
        yield current.strftime(PERIOD_FORMAT), upper.strftime(PERIOD_FORMAT)
        current = next_year


def _merge_window(
    old: pd.DataFrame, new: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    columns = list(dict.fromkeys([*old.columns, *new.columns]))
    new = new.reindex(index=pd.date_range(start, end, freq="h", name="period"), columns=columns)
    merged = pd.concat([old.reindex(columns=columns), new])
    merged = merged.loc[~merged.index.duplicated(keep="last")].sort_index()
    lower = min(start, merged.index.min())
    upper = max(end, merged.index.max())
    merged = merged.reindex(pd.date_range(lower, upper, freq="h", name="period")).astype("float64")
    merged.index = merged.index.astype("datetime64[ns, UTC]")
    return merged


def run_ingest(  # noqa: PLR0913, PLR0917
    region: str,
    start: str,
    end: str | None,
    settings: Settings,
    client: EiaClient | None = None,
    overlap_hours: int = 48,
) -> QualityReport:
    """Refresh an inclusive interval; new rows replace old rows, including nulls."""
    load_regions()[region]
    beginning = _hour(start)
    ending = _hour(end) if end is not None else pd.Timestamp.now(tz="UTC").floor("h")
    if beginning > ending or overlap_hours < 0:
        raise ValueError("start must not exceed end and overlap_hours must be nonnegative")
    cache_stage: Literal["raw", "interim"] = (
        "raw" if hourly_path(region, "raw", settings.data_dir).exists() else "interim"
    )
    old = (
        read_hourly(region, cache_stage, settings.data_dir)
        if hourly_path(region, cache_stage, settings.data_dir).exists()
        else pd.DataFrame()
    )
    fetch_start = beginning
    backfill = not old.empty and beginning < old.index.min()
    if not old.empty and beginning >= old.index.min():
        fetch_start = max(
            beginning, min(ending, old.index.max() - pd.Timedelta(hours=overlap_hours))
        )
    owned = client is None
    active = EiaClient(settings.require_eia_key()) if client is None else client
    merged = old.copy(deep=True)
    duplicates = 0
    source_region_rows = 0
    source_fuel_rows = 0
    try:
        for window_start, window_end in _year_windows(fetch_start, ending):
            region_rows = fetch_region_data(active, region, window_start, window_end)
            fuel_rows = fetch_fuel_type_data(active, region, window_start, window_end)
            new, window_duplicates = to_hourly_frame(region_rows, fuel_rows)
            duplicates += window_duplicates
            source_region_rows += len(region_rows)
            source_fuel_rows += len(fuel_rows)
            merged = _merge_window(merged, new, _hour(window_start), _hour(window_end))
            # Only checkpoint a complete pair of routes; a failed year leaves the
            # previous completed history available for an overlap-based retry.
            if not backfill:
                write_hourly(merged, region, "raw", settings.data_dir)
    finally:
        if owned:
            active.close()
    merged = merged.reindex(
        pd.date_range(
            min(beginning, merged.index.min()),
            max(ending, merged.index.max()),
            freq="h",
            name="period",
        ).astype("datetime64[ns, UTC]")
    )
    cleaned, report = validate_and_clean(merged)
    report = replace(report, n_duplicates=duplicates)
    unchanged = not old.empty and old.equals(merged)
    write_hourly(merged, region, "raw", settings.data_dir)
    interim_path = write_hourly(cleaned, region, "interim", settings.data_dir)
    diagnostics = {
        "region": region,
        "requested_start": beginning.isoformat(),
        "requested_end": ending.isoformat(),
        "fetch_start": fetch_start.isoformat(),
        "source_region_rows": source_region_rows,
        "source_fuel_rows": source_fuel_rows,
        "quality": asdict(report),
        "g2_pass": report.n_rows > 0 and report.gap_fraction < G2_MAX_GAP_FRACTION,
        "count_scope": "Cleaning and gaps cover merged data; duplicates count this fetch only.",
    }
    report_path = interim_path.with_name("quality-report.json")
    if not unchanged or not report_path.exists():
        report_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    return report
