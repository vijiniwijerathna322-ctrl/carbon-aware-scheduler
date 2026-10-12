"""Constraint, risk, arithmetic and historical-scoring regression tests."""

# ruff: noqa: PLR2004

from datetime import timedelta

import numpy as np
import pandas as pd

from carbon_scheduler.scheduler.models import Job
from carbon_scheduler.scheduler.optimizer import recommend

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


def test_interruptible() -> None:
    forecast = frame([100, 500, 50, 400])
    choice = recommend(job(2, 4, interruptible=True), forecast)
    assert choice.hours == [ISSUE, ISSUE + timedelta(hours=2)]
    assert choice.end <= job().deadline
    assert choice.emissions_gco2_median <= recommend(job(2, 4), forecast).emissions_gco2_median
