"""Replay fixed-arrival jobs against forecasts, observations and an oracle."""

from collections.abc import Sequence
from datetime import timedelta

import pandas as pd

from carbon_scheduler.models.base import utc_hour, validate_series
from carbon_scheduler.scheduler.models import Job, Strategy
from carbon_scheduler.scheduler.optimizer import feasible_hours, recommend, savings_pct


def make_jobs(
    issue_times: pd.DatetimeIndex,
    durations: Sequence[int] = (1, 2, 4, 8),
    windows_h: Sequence[int] = (6, 12, 24, 36),
    power_kw: float = 7.0,
) -> list[Job]:
    return [
        Job(
            duration_hours=duration,
            power_kw=power_kw,
            earliest_start=utc_hour(issue).to_pydatetime(),
            deadline=(issue + timedelta(hours=window)).to_pydatetime(),
        )
        for issue in issue_times
        for duration in durations
        for window in windows_h
        if window >= duration
    ]


def replay_scheduling(
    actual: pd.Series, forecasts: pd.DataFrame, jobs: Sequence[Job], strategy: Strategy
) -> pd.DataFrame:
    """Keep skipped rows; require complete actual support for fair oracle scoring.

    Forecasts start at h=1. The observed issue-hour value is supplied as h=0,
    under the existing zero observation latency assumption, before optimization.
    """
    validate_series(actual)
    if (actual.dropna() < 0).any():
        raise ValueError("Actual intensity must be nonnegative")
    if "issue_time" not in forecasts:
        raise ValueError("Forecasts require issue_time")
    groups = {issue: group.copy() for issue, group in forecasts.groupby("issue_time")}
    rows: list[dict[str, object]] = []
    for job in jobs:
        issue = pd.Timestamp(job.earliest_start)
        row: dict[str, object] = {
            "issue_time": issue,
            "duration_hours": job.duration_hours,
            "window_h": (job.deadline - job.earliest_start).total_seconds() / 3600,
            "strategy": strategy,
            "status": "skipped",
            "reason": "",
            **dict.fromkeys(
                (
                    "chosen_start",
                    "realized_gco2",
                    "baseline_gco2",
                    "oracle_gco2",
                    "savings_pct",
                    "oracle_savings_pct",
                    "regret_gco2",
                )
            ),
        }
        hours = feasible_hours(job)
        observed = actual.reindex(hours)
        if observed.isna().any():
            row["reason"] = "incomplete actual window"
        elif issue not in groups:
            row["reason"] = "missing issue forecast"
        else:
            frame = groups[issue]
            if (frame.target_time <= issue).any():
                raise ValueError("Backtest forecast targets must be after issue_time")
            if (
                "horizon" in frame
                and not (
                    frame.target_time == issue + pd.to_timedelta(frame.horizon, unit="h")
                ).all()
            ):
                raise ValueError("Forecast horizon and target_time disagree")
            current = float(actual.loc[issue])
            frame = pd.concat(
                [
                    pd.DataFrame(
                        {
                            "target_time": pd.Series([issue], dtype=frame.target_time.dtype),
                            "lower": [current],
                            "median": [current],
                            "upper": [current],
                        }
                    ),
                    frame[["target_time", "lower", "median", "upper"]],
                ],
                ignore_index=True,
            )
            try:
                choice = recommend(job, frame, strategy)
            except ValueError as error:
                row["reason"] = str(error)
            else:
                chosen_hours = (
                    pd.DatetimeIndex(choice.hours)
                    if choice.hours is not None
                    else pd.date_range(choice.start, periods=job.duration_hours, freq="h")
                )
                realized = float(actual.loc[chosen_hours].sum() * job.power_kw)
                baseline = float(observed.iloc[: job.duration_hours].sum() * job.power_kw)
                oracle = float(
                    (
                        observed.nsmallest(job.duration_hours).sum()
                        if job.interruptible
                        else observed.rolling(job.duration_hours).sum().min()
                    )
                    * job.power_kw
                )
                row.update(
                    status="scored",
                    chosen_start=choice.start,
                    realized_gco2=realized,
                    baseline_gco2=baseline,
                    oracle_gco2=oracle,
                    savings_pct=savings_pct(baseline, realized),
                    oracle_savings_pct=savings_pct(baseline, oracle),
                    regret_gco2=max(0.0, realized - oracle),
                )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_replay(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.loc[df.status == "scored"]
    rows = []
    for label, group in [*scored.groupby("window_h"), ("all", scored)]:
        rows.append(
            {
                "window_h": label,
                "n": len(group),
                "mean_savings_pct": group.savings_pct.mean(),
                "mean_oracle_savings_pct": group.oracle_savings_pct.mean(),
                "share_better_than_baseline": (group.realized_gco2 < group.baseline_gco2).mean(),
                "mean_regret_gco2": group.regret_gco2.mean(),
            }
        )
    return pd.DataFrame(rows).set_index("window_h")
