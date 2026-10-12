"""Offline backtest data selection, provenance and Markdown reports."""

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from carbon_scheduler.carbon.factors import load_emission_factors
from carbon_scheduler.carbon.intensity import compute_intensity
from carbon_scheduler.config import PROJECT_ROOT, Settings
from carbon_scheduler.ingest.store import hourly_path, read_hourly
from carbon_scheduler.models.backtest import BacktestConfig, rolling_origin_backtest
from carbon_scheduler.models.base import Forecaster, utc_hour
from carbon_scheduler.models.baselines import SeasonalNaiveForecaster
from carbon_scheduler.models.evaluate import coverage_table, coverage_verdict, summarize
from carbon_scheduler.regions import load_regions

TARGETS = ("demand_mwh", "carbon_intensity_g_per_kwh")


def load_backtest_series(
    region: str,
    target: str,
    settings: Settings,
    data_source: Literal["raw", "processed"] = "raw",
) -> tuple[pd.Series, dict[str, str]]:
    """Raw default avoids retrospective interpolation and centered filters.

    Snapshots contain latest revisions, not original publication vintages; this
    still assumes zero observation latency. Processed mode is exploratory only.
    """
    if target not in TARGETS:
        raise ValueError(f"target must be one of {TARGETS}")
    if data_source not in ("raw", "processed"):
        raise ValueError("data_source must be raw or processed")
    frame = read_hourly(region, data_source, settings.data_dir)
    metadata = {
        "data_source": data_source,
        "input_sha256": hashlib.sha256(
            hourly_path(region, data_source, settings.data_dir).read_bytes()
        ).hexdigest(),
        "limitations": (
            "Latest-revision snapshot; zero observation latency assumed; "
            "no publication-vintage archive."
        ),
    }
    if data_source == "processed":
        metadata["preprocessing"] = (
            "Exploratory retrospective cleaned data; not evidence for leakage-safe G3."
        )
    else:
        metadata["preprocessing"] = (
            "Pointwise raw observations; no interpolation or centered spike filtering."
        )
    if target == "carbon_intensity_g_per_kwh" and data_source == "raw":
        path = PROJECT_ROOT / "config/emission_factors.yaml"
        series = compute_intensity(frame, load_emission_factors(path))
        metadata["factors_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata["carbon_scope"] = (
            "Observed covered generation mix; partial fuel observations and excluded OTH; "
            "imports ignored."
        )
    else:
        if target not in frame:
            raise ValueError(f"Missing target column {target}; run build-dataset first")
        series = frame[target].astype("float64")
    if target == "demand_mwh":
        series = series.where(series > 0)
    if np.isinf(series.to_numpy()).any():
        raise ValueError("Target must be finite or NaN")
    if not series.notna().any():
        raise ValueError("No finite target observations available")
    return series, metadata


def _table(summary: pd.DataFrame) -> str:
    columns = list(summary.columns)
    lines = ["| bucket | " + " | ".join(columns) + " |", "|---|" + "---|" * len(columns)]
    for label, row in summary.iterrows():
        values = [
            "N/A"
            if pd.isna(row[column])
            else "PASS"
            if column == "g3_pass" and row[column]
            else "FAIL"
            if column == "g3_pass"
            else str(int(row[column]))
            if column in ("n", "n_interval")
            else f"{row[column]:.6f}"
            for column in columns
        ]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def render_backtest_report(
    summary_by_model: Mapping[str, pd.DataFrame],
    region: str,
    target: str,
    *,
    predictions_by_model: Mapping[str, pd.DataFrame] | None = None,
) -> str:
    lines = [f"# Rolling-origin backtest: {region} / {target}", ""]
    for name, summary in summary_by_model.items():
        lines.extend(
            [
                f"## {name}",
                "",
                f"Test interval (UTC): {summary.attrs.get('test_start', 'unspecified')} to "
                f"{summary.attrs.get('test_end', 'unspecified')}.",
                "",
                "Daily region-local midnight issues; refit every 30 local calendar days. "
                "Targets beyond the test end are unscored. n counts finite point pairs; "
                "n_interval counts finite observed interval pairs. "
                + (
                    "CQR intervals use a separate earlier calibration window."
                    if name == "cqr"
                    else "Intervals are uncalibrated."
                ),
                "",
                _table(summary),
                "",
            ]
        )
        if name == "cqr" and predictions_by_model is not None:
            lines.extend(
                [
                    f"G4: {'PASS' if coverage_verdict(summary) else 'FAIL'} "
                    "(overall 77–83%; each horizon bucket ≥70%).",
                    "",
                ]
            )
            for grouping in ("horizon_bucket", "hour_local", "month_local"):
                coverage = coverage_table(
                    predictions_by_model[name], grouping, summary.attrs.get("timezone", "UTC")
                )
                lines.extend([f"### Coverage by {grouping}", "", _table(coverage), ""])
        for key, value in summary.attrs.items():
            if key not in ("test_start", "test_end"):
                lines.append(f"- {key}: {value}")
        lines.append("")
    return "\n".join(lines)


def run_backtest(  # noqa: PLR0913
    region: str,
    target: str,
    model: str,
    settings: Settings,
    *,
    reports_dir: Path = Path("reports"),
    data_source: Literal["raw", "processed"] = "raw",
    test_start: pd.Timestamp | None = None,
    test_end: pd.Timestamp | None = None,
) -> Path:
    """Run the last six calendar months by default and persist predictions/report."""
    if model not in ("naive", "lgbm", "cqr"):
        raise ValueError("model must be naive, lgbm or cqr")
    timezone = load_regions()[region].timezone
    series, metadata = load_backtest_series(region, target, settings, data_source)
    end = utc_hour(test_end) if test_end is not None else pd.Timestamp(series.index[-1])
    start = (
        utc_hour(test_start)
        if test_start is not None
        else max(
            pd.Timestamp(series.index[0]) + pd.Timedelta(hours=168),
            end - pd.DateOffset(months=6),
        )
    )
    if end > series.index[-1] or start < series.index[0] or start >= end:
        raise ValueError(
            "Test bounds must lie within available history and leave seasonal training history"
        )
    factory: Callable[[], Forecaster]
    if model == "naive":
        factory = SeasonalNaiveForecaster
    elif model == "cqr":
        from carbon_scheduler.models.forecast_model import ForecastModel  # noqa: PLC0415

        factory = lambda: ForecastModel(target, timezone)  # noqa: E731
    else:
        from carbon_scheduler.models.lgbm import LgbmForecaster  # noqa: PLC0415

        factory = lambda: LgbmForecaster(timezone)  # noqa: E731
    prediction = rolling_origin_backtest(series, factory, BacktestConfig(start, end, timezone))
    summary = summarize(prediction)
    summary.attrs.update(
        metadata, test_start=start.isoformat(), test_end=end.isoformat(), timezone=timezone
    )
    if model in ("lgbm", "cqr"):
        from carbon_scheduler.models.lgbm import DEFAULT_PARAMS  # noqa: PLC0415

        summary.attrs["model_parameters"] = json.dumps(
            {**DEFAULT_PARAMS, "seed": 42, "n_jobs": 1, "issue_step_h": 3}, sort_keys=True
        )
    if model == "cqr":
        summary.attrs["calibration_days"] = 90
    directory = reports_dir if reports_dir.is_absolute() else PROJECT_ROOT / reports_dir
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / f"backtest_{region}_{target}_{model}"
    prediction.to_parquet(stem.with_suffix(".parquet"), index=False)
    path = stem.with_suffix(".md")
    path.write_text(
        render_backtest_report(
            {model: summary}, region, target, predictions_by_model={model: prediction}
        ),
        encoding="utf-8",
    )
    stem.with_suffix(".json").write_text(
        json.dumps(dict(summary.attrs), indent=2, sort_keys=True), encoding="utf-8"
    )
    return path
