"""Constraint, risk, arithmetic and historical-scoring regression tests."""

# ruff: noqa: PLR2004

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.scheduler.models import Job
from carbon_scheduler.scheduler.optimizer import InsufficientForecastError, recommend

ISSUE = pd.Timestamp("2026-01-01", tz="UTC")


def job(duration: int = 1, window: int = 4, **kwargs: object) -> Job:
    values = dict(
        duration_hours=duration,
        power_kw=10,
        earliest_start=ISSUE,
        deadline=ISSUE + timedelta(hours=window),
    )
    values.update(kwargs)
    return Job.model_validate(values)


def frame(values: list[float], upper: list[float] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "target_time": pd.date_range(ISSUE, periods=len(values), freq="h"),
            "lower": np.array(values) - 10,
            "median": values,
            "upper": np.array(values) + 10 if upper is None else upper,
        }
    )


def test_cleanest_window_arithmetic_and_bounds() -> None:
    choice = recommend(job(2, 4), frame([400, 100, 200, 500]))
    assert choice.start == ISSUE + timedelta(hours=1)
    assert choice.end <= job().deadline
    assert choice.emissions_gco2_median == 3000
    assert choice.emissions_gco2_lower == 2800
    assert choice.emissions_gco2_upper == 3200
    assert choice.expected_savings_pct == 40


@pytest.mark.parametrize(
    "duration,window,values", [(1, 4, [100.0] * 4), (2, 2, [100.0, 200.0]), (1, 4, [0.0] * 4)]
)
def test_ties_single_window_and_zero(duration: int, window: int, values: list[float]) -> None:
    choice = recommend(job(duration, window), frame(values))
    assert choice.start == ISSUE
    assert choice.expected_savings_pct == 0
    assert choice.emissions_gco2_lower >= 0


def test_off_hour_ceil_and_deadline() -> None:
    choice = recommend(
        job(1, 3, earliest_start=ISSUE + timedelta(minutes=1)), frame([0, 200, 100, 0])
    )
    assert choice.start == ISSUE + timedelta(hours=2)
    with pytest.raises(ValueError, match="whole-hour"):
        recommend(
            job(
                1,
                2,
                earliest_start=ISSUE + timedelta(minutes=1),
                deadline=ISSUE + timedelta(hours=1, minutes=1),
            ),
            frame([100, 100]),
        )


def test_missing_coverage() -> None:
    with pytest.raises(InsufficientForecastError, match="2 required hours"):
        recommend(job(), frame([100, 100]))


def test_nan_windows() -> None:
    choice = recommend(job(), frame([100, np.nan, 50, 100]))
    assert choice.start == ISSUE + timedelta(hours=2)
    with pytest.raises(ValueError, match="baseline"):
        recommend(job(), frame([np.nan] * 4))


@pytest.mark.parametrize("problem", ["bounds", "negative", "infinite", "gap", "naive"])
def test_malformed_forecast(problem: str) -> None:
    forecast = frame([100.0, 200.0, 300.0, 400.0])
    if problem == "bounds":
        forecast.loc[0, "lower"] = 200.0
    elif problem == "negative":
        forecast.loc[0, ["lower", "median", "upper"]] = [-30.0, -20.0, -10.0]
    elif problem == "infinite":
        forecast.loc[0, "upper"] = np.inf
    elif problem == "gap":
        forecast = forecast.drop(index=1)
    else:
        forecast["target_time"] = forecast.target_time.dt.tz_localize(None)
    with pytest.raises(ValueError):
        recommend(job(), forecast)
