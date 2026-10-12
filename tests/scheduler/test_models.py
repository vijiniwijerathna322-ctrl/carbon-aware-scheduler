"""Constraint, risk, arithmetic and historical-scoring regression tests."""

# ruff: noqa: PLR2004

from datetime import timedelta

import pandas as pd
import pytest
from pydantic import ValidationError

from carbon_scheduler.scheduler.models import Job

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


@pytest.mark.parametrize(
    "kwargs",
    [
        {"earliest_start": ISSUE.tz_localize(None)},
        {"deadline": ISSUE.tz_localize(None)},
        {"power_kw": 0},
        {"power_kw": -1},
        {"power_kw": float("inf")},
        {"duration_hours": 0},
        {"duration_hours": 169},
        {"duration_hours": True},
        {"deadline": ISSUE},
    ],
)
def test_invalid_job(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        job(**kwargs)


def test_normalizes_timezone() -> None:
    value = job(earliest_start=ISSUE.tz_convert("Asia/Colombo"))
    assert str(value.earliest_start.tzinfo) == "UTC"
