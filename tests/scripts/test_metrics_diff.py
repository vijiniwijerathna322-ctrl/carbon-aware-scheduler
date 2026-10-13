import json
from pathlib import Path
from runpy import run_path

import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.reporting import TARGETS

helpers = run_path(str(Path(__file__).resolve().parents[2] / "scripts/metrics_diff.py"))
build_review = helpers["build_review"]
metrics_diff = helpers["metrics_diff"]
paired_metrics = helpers["paired_metrics"]


def test_diff_shows_deltas_and_marks_regressions():
    result = metrics_diff(
        {"mae": 10, "coverage": 0.8, "mean_width": 5},
        {"mae": 12, "coverage": 0.7, "mean_width": 4},
    )
    assert "| mae | 10.0000 | 12.0000 | +2.0000 | regression |" in result
    assert "| coverage | 0.8000 | 0.7000 | -0.1000 | regression |" in result
    assert "| mean_width | 5.0000 | 4.0000 | -1.0000 | review |" in result


def test_missing_old_metrics_handled():
    result = metrics_diff({}, {"mae": 12, "coverage": None})
    assert "| mae | N/A | 12.0000 | N/A | no comparison |" in result
    assert "nan" not in result.lower()


def test_coverage_improvement_uses_distance_from_nominal():
    result = metrics_diff({"coverage": 0.95}, {"coverage": 0.85})
    assert "improvement" in result


def _predictions():
    issues = pd.date_range("2024-01-01", periods=120, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "issue_time": issues,
            "target_time": issues + pd.Timedelta(hours=1),
            "horizon": 1,
            "y": np.arange(len(issues), dtype=float),
            "median": np.arange(len(issues), dtype=float) + 1,
            "lower": np.arange(len(issues), dtype=float) - 2,
            "upper": np.arange(len(issues), dtype=float) + 2,
        }
    )


def test_paired_metrics_exclude_different_labels_and_unmatched_rows():
    old, new = _predictions(), _predictions()
    new.loc[0, "y"] += 3
    new.loc[1, "median"] = np.nan
    new = new.iloc[:-1]
    previous, candidate, counts = paired_metrics(old, new)
    assert previous["all"]["mae"] == candidate["all"]["mae"]
    assert counts["paired_finite_rows"] == 117  # noqa: PLR2004
    assert counts["different_labels"] == 1
    assert counts["excluded_nonfinite"] == 1
    assert counts["unmatched_old"] == 1


def test_duplicate_forecast_keys_and_too_few_points_rejected():
    pred = _predictions()
    with pytest.raises(ValueError, match="unique"):
        paired_metrics(pd.concat([pred, pred.iloc[:1]]), pred)
    with pytest.raises(ValueError, match="100"):
        paired_metrics(pred.iloc[:2], pred.iloc[:2])


@pytest.mark.parametrize("with_previous", [False, True])
def test_review_artifacts_include_scope_provenance_and_regressions(tmp_path, with_previous):
    old_dir, new_dir, output = (tmp_path / name for name in ("old", "new", "output"))
    new_dir.mkdir()
    if with_previous:
        old_dir.mkdir()
    for target in TARGETS:
        name = f"backtest_CISO_{target}_cqr"
        metadata = {"data_source": "raw", "timezone": "America/Los_Angeles"}
        prediction = _predictions()
        if with_previous:
            prediction.to_parquet(old_dir / f"{name}.parquet", index=False)
            (old_dir / f"{name}.json").write_text(json.dumps(metadata), encoding="utf-8")
        prediction["median"] += 1
        prediction.to_parquet(new_dir / f"{name}.parquet", index=False)
        (new_dir / f"{name}.json").write_text(json.dumps(metadata), encoding="utf-8")
    build_review("CISO", old_dir, new_dir, output)
    body = (output / "review.md").read_text(encoding="utf-8")
    assert "not the latest artifact" in body
    assert "does not change deployed model pointers" in body
    assert ("regression" if with_previous else "no comparison") in body
    payload = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert payload["provenance"][TARGETS[0]]["new"]["data_source"] == "raw"


def test_review_rejects_weather_results(tmp_path):
    name = f"backtest_CISO_{TARGETS[0]}_cqr.json"
    (tmp_path / name).write_text(
        json.dumps({"data_source": "raw", "exog_columns": ["temperature"]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="weather-free"):
        build_review("CISO", None, tmp_path, tmp_path / "output")
