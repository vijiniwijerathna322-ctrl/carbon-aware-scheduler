"""Rank per-forecast feature contributions for presentation."""

from dataclasses import dataclass

import pandas as pd

from carbon_scheduler.models.forecast_model import ForecastModel

DEFAULT_TOP_N = 8


@dataclass(frozen=True)
class Contribution:
    feature: str
    value: float
    contribution: float


@dataclass(frozen=True)
class HorizonExplanation:
    target_time: pd.Timestamp
    horizon: int
    base_value: float
    raw_median: float
    contributions: tuple[Contribution, ...]


def explain_forecast(  # noqa: PLR0913, PLR0917
    model: ForecastModel,
    series: pd.Series,
    issue_time: pd.Timestamp,
    exog: pd.DataFrame | None = None,
    horizon: int | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> list[HorizonExplanation]:
    """Top-`top_n` feature contributions per horizon, sorted by |contribution|.

    `raw_median` sums *all* feature contributions (not just the returned
    top-N) plus the base value, so it reproduces the median booster's raw
    prediction regardless of how many contributions are kept for display.
    """
    long = model.explain(series, issue_time, exog)
    if horizon is not None:
        long = long.loc[long["horizon"] == horizon]
    results = []
    for _, group in long.groupby(["target_time", "horizon"], sort=True):
        base_value = float(group["base_value"].iloc[0])
        raw_median = base_value + float(group["contribution"].sum())
        ranked = group.reindex(group["contribution"].abs().sort_values(ascending=False).index)
        top = ranked.head(top_n)
        contributions = tuple(
            Contribution(feature=str(feature), value=float(value), contribution=float(contrib))
            for feature, value, contrib in zip(
                top["feature"], top["value"], top["contribution"], strict=True
            )
        )
        results.append(
            HorizonExplanation(
                target_time=pd.Timestamp(group["target_time"].iloc[0]),
                horizon=int(group["horizon"].iloc[0]),
                base_value=base_value,
                raw_median=raw_median,
                contributions=contributions,
            )
        )
    return sorted(results, key=lambda result: result.horizon)
