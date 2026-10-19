"""Fixed earlier-period CISO carbon calibration partition comparison; no promotion."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_scheduler.config import get_settings
from carbon_scheduler.models.backtest import BacktestConfig, rolling_origin_backtest
from carbon_scheduler.models.conformal import SplitConformalCQR
from carbon_scheduler.models.evaluate import coverage_verdict, summarize
from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.reporting import load_backtest_series

START = pd.Timestamp("2025-03-01T08:00:00Z")
END = pd.Timestamp("2025-03-31T07:00:00Z")
KEYS = ["issue_time", "target_time", "horizon"]


def make_variant(per_horizon: bool) -> ForecastModel:
    model = ForecastModel("carbon_intensity_g_per_kwh", "America/Los_Angeles")
    if per_horizon:
        model.calibrator = SplitConformalCQR(buckets=tuple((h, h) for h in range(1, 49)))
    return model


def compare_variants(series: pd.Series, provenance: dict, output: Path) -> dict:
    """Truncate the snapshot before evaluation and require identical point forecasts."""
    history = series.loc[:END].copy()
    cfg = BacktestConfig(START, END, "America/Los_Angeles", retrain_every_days=31)
    predictions = {}
    for name, per_horizon in (("bucket", False), ("per_horizon", True)):
        predictions[name] = rolling_origin_backtest(
            history, lambda per_horizon=per_horizon: make_variant(per_horizon), cfg
        )
    baseline, candidate = predictions["bucket"], predictions["per_horizon"]
    if not baseline[KEYS].equals(candidate[KEYS]):
        raise ValueError("Calibration variants must share forecast keys")
    for column in ("y", "median"):
        if not np.allclose(baseline[column], candidate[column], equal_nan=True):
            raise ValueError(f"Calibration variants must share identical {column}")
    results = {}
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in predictions.items():
        summary = summarize(frame)
        frame.to_parquet(output / f"{name}.parquet", index=False)
        results[name] = {
            "summary": summary.to_dict(orient="index"),
            "g4_pass": coverage_verdict(summary),
        }
    payload = {
        "scope": "Exploratory March 2025 CISO carbon partition comparison; no promotion",
        "validation_start": START.isoformat(),
        "validation_end": END.isoformat(),
        "source_provenance": provenance,
        "fixed": {"calibration_days": 90, "seed": 42, "issue_step_h": 3, "alpha": 0.2},
        "variants": results,
        "limitations": "Latest-revision data, one earlier month, dependent hourly outcomes. "
        "No confirmatory future-performance or production acceptance claim.",
    }
    (output / "comparison.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    return payload


def main() -> None:
    series, provenance = load_backtest_series("CISO", "carbon_intensity_g_per_kwh", get_settings())
    compare_variants(series, provenance, Path("reports/carbon-horizon-experiment"))


if __name__ == "__main__":
    main()
