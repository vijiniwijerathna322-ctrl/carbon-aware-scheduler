"""Atomic, idempotent Parquet storage for hourly region frames."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

import pandas as pd

from carbon_scheduler.regions import load_regions


def _check_index(df: pd.DataFrame) -> None:
    index = df.index
    if not isinstance(index, pd.DatetimeIndex) or str(index.tz) != "UTC":
        raise ValueError("Stored index must be a UTC DatetimeIndex")
    if index.name != "period" or str(index.dtype) != "datetime64[ns, UTC]":
        raise ValueError("Stored index must be named period with nanosecond UTC timestamps")
    if index.hasnans or not index.equals(index.floor("h")):
        raise ValueError("Stored index must contain valid whole hours")
    if len(index) and not index.equals(pd.date_range(index[0], periods=len(index), freq="h")):
        raise ValueError("Stored index must be regular, unique and increasing")


def hourly_path(region: str, stage: str, data_dir: Path) -> Path:
    if stage not in ("raw", "interim", "processed"):
        raise ValueError("stage must be raw, interim or processed")
    load_regions()[region]
    return data_dir / stage / region / "hourly.parquet"


def write_hourly(
    df: pd.DataFrame, region: str, stage: Literal["raw", "interim", "processed"], data_dir: Path
) -> Path:
    """Replace a complete file atomically; equal frames leave bytes untouched."""
    _check_index(df)
    path = hourly_path(region, stage, data_dir)
    if path.exists() and pd.read_parquet(path).equals(df):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as temporary:
        temp_path = Path(temporary.name)
    try:
        df.to_parquet(temp_path, engine="pyarrow", index=True)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path


def read_hourly(
    region: str, stage: Literal["raw", "interim", "processed"], data_dir: Path
) -> pd.DataFrame:
    """Read a stored frame, with actionable instructions if absent."""
    path = hourly_path(region, stage, data_dir)
    if not path.is_file():
        raise FileNotFoundError(f"No hourly data at {path}; run carbon-scheduler ingest first")
    frame = pd.read_parquet(path)
    _check_index(frame)
    return frame
