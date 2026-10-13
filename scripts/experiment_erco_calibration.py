"""Exploratory calibration-window comparison before the inspected 2026 test period."""

import json
from pathlib import Path

import pandas as pd

from carbon_scheduler.config import get_settings
from carbon_scheduler.models.backtest import BacktestConfig, rolling_origin_backtest
from carbon_scheduler.models.evaluate import coverage_verdict, summarize
from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.reporting import load_backtest_series


def main() -> None:
    settings = get_settings()
    series, provenance = load_backtest_series("ERCO", "demand_mwh", settings)
    # Freeze dates independently of the previously inspected Apr-Oct 2026 test.
    start = pd.Timestamp("2025-03-01T06:00:00Z")
    end = pd.Timestamp("2025-03-31T05:00:00Z")
    history = series.loc[:end].copy()
    output = Path("reports/erco-calibration-experiment")
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for days in (90, 180):
        predictions = rolling_origin_backtest(
            history,
            lambda days=days: ForecastModel("demand_mwh", "America/Chicago", calibration_days=days),
            BacktestConfig(start, end, "America/Chicago", retrain_every_days=31),
        )
        summary = summarize(predictions)
        predictions.to_parquet(output / f"calibration-{days}.parquet", index=False)
        results[str(days)] = {
            "summary": summary.to_dict(orient="index"),
            "g4_pass": coverage_verdict(summary),
        }
    payload = {
        "scope": "Exploratory earlier-period comparison; no promotion or confirmatory claim",
        "region": "ERCO",
        "target": "demand_mwh",
        "validation_start": start.isoformat(),
        "validation_end": end.isoformat(),
        "history_truncated_at": end.isoformat(),
        "source_provenance": provenance,
        "fixed_parameters": {"seed": 42, "issue_step_h": 3, "alpha": 0.2},
        "variants": results,
        "limitations": "Longer calibration also moves the training cutoff; this is a pipeline comparison. "
        "One earlier month cannot establish deployment coverage. Final future validation remains required.",
    }
    (output / "comparison.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
