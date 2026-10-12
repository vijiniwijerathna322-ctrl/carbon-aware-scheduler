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


def test_risk_strategies() -> None:
    forecast = frame([100, 120], [400, 150])
    assert recommend(job(1, 2), forecast).start == ISSUE
    assert recommend(job(1, 2), forecast, "upper").start == ISSUE + timedelta(hours=1)
    assert (
        recommend(job(), frame([300, 100, 200, 500])).start
        == recommend(job(), frame([300, 100, 200, 500]), "upper").start
    )
