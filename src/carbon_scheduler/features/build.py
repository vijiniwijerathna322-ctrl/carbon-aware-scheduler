"""Vectorized direct multi-horizon supervised features."""

from collections.abc import Sequence

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from carbon_scheduler.models.base import HORIZONS, validate_horizons, validate_series

FEATURE_COLUMNS = [
    "horizon",
    "y_issue",
    "y_lag1",
    "y_lag24",
    "roll_mean_24",
    "roll_std_24",
    "anchor_24",
    "anchor_168",
    "hour_local",
    "dow_local",
    "month_local",
    "is_us_holiday",
]


def build_supervised(
    series: pd.Series,
    issue_times: pd.DatetimeIndex,
    *,
    tz: str,
    horizons: Sequence[int] = HORIZONS,
    with_target: bool = True,
) -> pd.DataFrame:
    """Calendar features describe targets; observation features describe issues.

    Rolling windows include the issue observation and require all 24 values.
    Missing lag/anchor observations are never replaced by future observations.
    """
    validate_series(series)
    hs = validate_horizons(horizons)
    if (
        issue_times.tz is None
        or issue_times.hasnans
        or not issue_times.equals(issue_times.floor("h"))
    ):
        raise ValueError("Issue times must be timezone-aware whole hours")
    issues = issue_times.tz_convert("UTC").repeat(len(hs))
    horizon = np.tile(hs, len(issue_times))
    targets = issues + pd.to_timedelta(horizon, unit="h")
    local = targets.tz_convert(tz)
    days = local.tz_localize(None).normalize()
    holidays = (
        USFederalHolidayCalendar().holidays(days.min(), days.max())
        if len(days)
        else pd.DatetimeIndex([])
    )
    frame = pd.DataFrame({"issue_time": issues, "target_time": targets, "horizon": horizon})
    frame["y_issue"] = series.reindex(issues).to_numpy()
    frame["y_lag1"] = series.reindex(issues - pd.Timedelta(hours=1)).to_numpy()
    frame["y_lag24"] = series.reindex(issues - pd.Timedelta(hours=24)).to_numpy()
    frame["roll_mean_24"] = series.rolling(24, min_periods=24).mean().reindex(issues).to_numpy()
    frame["roll_std_24"] = series.rolling(24, min_periods=24).std().reindex(issues).to_numpy()
    for season in (24, 168):
        offset = season * ((horizon + season - 1) // season)
        anchors = targets - pd.to_timedelta(offset, unit="h")
        frame[f"anchor_{season}"] = series.reindex(anchors).to_numpy()
    frame["hour_local"] = local.hour
    frame["dow_local"] = local.dayofweek
    frame["month_local"] = local.month
    frame["is_us_holiday"] = days.isin(holidays).astype(int)
    frame["y"] = series.reindex(targets).to_numpy() if with_target else np.nan
    return frame
