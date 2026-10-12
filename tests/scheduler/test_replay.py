"""Constraint, risk, arithmetic and historical-scoring regression tests."""

# ruff: noqa: PLR2004

import numpy as np
import pandas as pd

from carbon_scheduler.scheduler.replay import make_jobs, replay_scheduling, summarize_replay

ISSUE = pd.Timestamp("2026-01-01", tz="UTC")


def frame(values: list[float], upper: list[float] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "target_time": pd.date_range(ISSUE, periods=len(values), freq="h"),
            "lower": np.array(values) - 10,
            "median": values,
            "upper": np.array(values) + 10 if upper is None else upper,
        }
    )


def replay(values: list[float], prediction: list[float], duration: int = 1) -> pd.DataFrame:
    actual = pd.Series(values, index=pd.date_range(ISSUE, periods=len(values), freq="h"))
    forecasts = frame(prediction).iloc[1:].assign(issue_time=ISSUE)
    jobs = make_jobs(
        pd.DatetimeIndex([ISSUE]), durations=(duration,), windows_h=(len(values),), power_kw=10
    )
    return replay_scheduling(actual, forecasts, jobs, "median")


def test_perfect_replay_and_oracle() -> None:
    result = replay([300, 100, 200, 400], [300, 100, 200, 400])
    assert result.iloc[0].regret_gco2 == 0
    assert result.iloc[0].oracle_gco2 <= result.iloc[0].baseline_gco2
    summary = summarize_replay(result)
    assert summary.loc["all", "n"] == 1
    assert set(summary) == {
        "n",
        "mean_savings_pct",
        "mean_oracle_savings_pct",
        "share_better_than_baseline",
        "mean_regret_gco2",
    }


def test_realized_actual_and_single_window() -> None:
    result = replay([300, 500, 100, 400], [300, 50, 200, 400])
    assert result.iloc[0].realized_gco2 == 5000
    assert result.iloc[0].savings_pct < 0
    assert result.iloc[0].oracle_gco2 <= result.iloc[0].realized_gco2
    assert replay([100, 200], [100, 200], duration=2).iloc[0].savings_pct == 0


def test_incomplete_actual_skipped() -> None:
    result = replay([300, 100, np.nan, 400], [300, 100, 200, 400])
    assert result.iloc[0].status == "skipped"
    assert result.iloc[0].reason == "incomplete actual window"
    assert summarize_replay(result).loc["all", "n"] == 0
