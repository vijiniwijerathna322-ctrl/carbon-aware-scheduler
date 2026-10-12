"""Choose whole-hour jobs with explicit forecast coverage checks."""

from datetime import timedelta
from typing import cast

import pandas as pd

from carbon_scheduler.models.base import validate_series
from carbon_scheduler.scheduler.models import Job, Recommendation, Strategy


class InsufficientForecastError(ValueError):
    """The forecast does not cover all feasible job hours."""


def savings_pct(baseline: float, chosen: float) -> float:
    """Percentage reduction; zero baseline uses a documented zero convention."""
    return 100 * (baseline - chosen) / baseline if baseline else 0.0


def feasible_hours(job: Job) -> pd.DatetimeIndex:
    start = pd.Timestamp(job.earliest_start).ceil("h")
    end = pd.Timestamp(job.deadline).floor("h")
    count = max(0, int((end - start) / pd.Timedelta(hours=1)))
    hours = pd.date_range(start, periods=count, freq="h")
    if len(hours) < job.duration_hours:
        raise ValueError("No whole-hour window fits before the deadline")
    return hours


def recommend(job: Job, forecast: pd.DataFrame, strategy: Strategy = "median") -> Recommendation:
    if strategy not in ("median", "upper"):
        raise ValueError("Strategy must be median or upper")
    required = {"target_time", "lower", "median", "upper"}
    if not required.issubset(forecast.columns):
        raise ValueError("Forecast requires target_time, lower, median and upper")
    frame = forecast.set_index("target_time")[["lower", "median", "upper"]].copy()
    for column in frame:
        validate_series(frame[column])
    complete = frame.dropna()
    if ((complete.lower > complete["median"]) | (complete["median"] > complete.upper)).any():
        raise ValueError("Forecast bounds must be ordered")
    if (complete[["median", "upper"]] < 0).any().any():
        raise ValueError("Median and upper carbon intensity must be nonnegative")
    frame["lower"] = frame.lower.clip(lower=0)
    hours = feasible_hours(job)
    missing = len(hours.difference(pd.DatetimeIndex(frame.index)))
    if missing:
        raise InsufficientForecastError(f"Forecast is missing {missing} required hours")
    available = frame.loc[hours]
    duration = job.duration_hours
    baseline = available.iloc[:duration]
    if baseline.isna().any().any():
        raise ValueError("Run-now baseline contains missing forecast values")
    if job.interruptible:
        valid = available.dropna()
        if len(valid) < duration:
            raise ValueError("Not enough valid forecast hours for the job")
        selected = valid.nsmallest(duration, strategy, keep="first").sort_index()
    else:
        sums = available.rolling(duration, min_periods=duration).sum().dropna()
        if sums.empty:
            raise ValueError("All candidate windows contain missing forecast values")
        end_hour = cast(pd.Timestamp, sums[strategy].idxmin())
        selected = available.loc[end_hour - timedelta(hours=duration - 1) : end_hour]
    emissions = selected.sum() * job.power_kw
    baseline_emissions = float(baseline["median"].sum() * job.power_kw)
    start = selected.index[0]
    return Recommendation(
        start=start.to_pydatetime(),
        end=(selected.index[-1] + timedelta(hours=1)).to_pydatetime(),
        strategy=strategy,
        emissions_gco2_median=float(emissions["median"]),
        emissions_gco2_lower=float(emissions["lower"]),
        emissions_gco2_upper=float(emissions["upper"]),
        baseline_start=hours[0].to_pydatetime(),
        baseline_emissions_gco2_median=baseline_emissions,
        expected_savings_pct=savings_pct(baseline_emissions, float(emissions["median"])),
        delay_hours=int((start - hours[0]) / pd.Timedelta(hours=1)),
        hours=[hour.to_pydatetime() for hour in selected.index] if job.interruptible else None,
    )
