# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.evaluate import compare_point_forecasts, coverage_table, summarize


def test_summarize_buckets_and_counts():
    frame = pd.DataFrame(
        {
            "horizon": [1, 7, 25, 48],
            "y": [1.0, 2, 3, np.nan],
            "median": [1.0, 3, 5, 1],
            "lower": [0.0, 0, 0, 0],
            "upper": [2.0, 4, 6, 2],
        }
    )
    result = summarize(frame)
    assert list(result.index) == ["1-6", "7-24", "25-48", "all"]
    assert result.loc["all", "n"] == 3
    assert result.loc["all", "mae"] == 1
    assert result.loc["all", "coverage"] == 1
    assert result.loc["25-48", "n"] == 1
    assert result.loc["all", "n_interval"] == 3


def test_point_only_and_missing_predictions_are_not_counted():
    frame = pd.DataFrame(
        {
            "horizon": [1, 2],
            "y": [1, 2],
            "median": [1, np.nan],
            "lower": [np.nan, np.nan],
            "upper": [np.nan, np.nan],
        }
    )
    result = summarize(frame)
    assert result.loc["all", "n"] == 1
    assert result.loc["all", "n_interval"] == 0
    assert pd.isna(result.loc["all", "coverage"])
    assert pd.isna(result.loc["7-24", "mae"])


def test_invalid_alpha_raises():
    with pytest.raises(ValueError, match="alpha"):
        summarize(pd.DataFrame(), alpha=0)


def test_g3_pairs_same_predictions_and_excludes_missing_baseline():
    base = pd.DataFrame(
        {
            "issue_time": [1, 1],
            "target_time": [2, 3],
            "horizon": [1, 2],
            "y": [0.0, 1000],
            "median": [10.0, np.nan],
        }
    )
    model = base.copy()
    model["median"] = [5.0, 0.0]
    result = compare_point_forecasts(base, model)
    assert result.loc["all", "n"] == 1
    assert result.loc["all", "improvement_percent"] == 50
    assert result.loc["1-6", "g3_pass"]
    assert not result.loc["7-24", "g3_pass"]
    with pytest.raises(ValueError, match="keys"):
        compare_point_forecasts(base, model.iloc[:1])
    model.loc[0, "y"] = 3.0
    with pytest.raises(ValueError, match="labels"):
        compare_point_forecasts(base, model)


def test_coverage_table_known_values_and_complete_hour_grid():
    pred = pd.DataFrame(
        {
            "target_time": pd.to_datetime(["2024-01-01T08Z", "2024-01-01T09Z"], utc=True),
            "horizon": [1, 7],
            "y": [1.0, 5.0],
            "lower": [0.0, 0.0],
            "upper": [2.0, 2.0],
        }
    )
    hourly = coverage_table(pred, "hour_local", "America/Los_Angeles")
    assert len(hourly) == 24
    assert hourly.loc[0, "coverage"] == 1
    assert hourly.loc[1, "coverage"] == 0
    assert pd.isna(hourly.loc[2, "coverage"])
    buckets = coverage_table(pred, "horizon_bucket", "UTC")
    assert buckets.loc["all", "coverage"] == 0.5
    assert buckets.loc["all", "mean_width"] == 2
