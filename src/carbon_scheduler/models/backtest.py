"""Rolling-origin evaluation with physical information-boundary truncation."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from carbon_scheduler.models.base import Forecaster, utc_hour, validate_series

logger = logging.getLogger(__name__)
PREDICTION_COLUMNS = ["target_time", "horizon", "lower", "median", "upper"]
BACKTEST_COLUMNS = ["issue_time", *PREDICTION_COLUMNS, "y"]


@dataclass(frozen=True)
class BacktestConfig:
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    tz: str
    issue_hour_local: int = 0
    retrain_every_days: int = 30

    def __post_init__(self) -> None:
        ZoneInfo(self.tz)
        if utc_hour(self.test_start) > utc_hour(self.test_end):
            raise ValueError("test_start must not exceed test_end")
        if not 0 <= self.issue_hour_local < 24:  # noqa: PLR2004
            raise ValueError("issue_hour_local must be in 0..23")
        if self.retrain_every_days < 1:
            raise ValueError("retrain_every_days must be positive")


def _issue_times(cfg: BacktestConfig) -> pd.DatetimeIndex:
    start = cfg.test_start.tz_convert(cfg.tz).normalize().tz_localize(None)
    end = cfg.test_end.tz_convert(cfg.tz).normalize().tz_localize(None)
    local = pd.date_range(start, end, freq="D") + pd.Timedelta(hours=cfg.issue_hour_local)
    # A nonexistent or ambiguous configured clock hour is skipped, rather than
    # inventing a forecast or duplicating an issue. Local midnight is unambiguous.
    issues = (
        local.tz_localize(cfg.tz, nonexistent="NaT", ambiguous="NaT").dropna().tz_convert("UTC")
    )
    return issues[(issues >= cfg.test_start) & (issues <= cfg.test_end)]


def _validate_prediction(pred: pd.DataFrame, issue: pd.Timestamp) -> None:
    if set(PREDICTION_COLUMNS) - set(pred):
        raise ValueError("Forecast is missing required prediction columns")
    horizons = pred.horizon.to_numpy()
    if pred.empty or pred.horizon.duplicated().any() or not np.isin(horizons, range(1, 49)).all():
        raise ValueError("Forecast horizons must be unique integers in 1..48")
    expected = pd.Series(issue + pd.to_timedelta(horizons, unit="h"), index=pred.index)
    if not pred.target_time.equals(expected):
        raise ValueError("Forecast target_time must equal issue_time plus horizon")
    values = pred[["lower", "median", "upper"]].to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError("Forecast values must be finite or NaN")
    if ((pred.lower > pred["median"]) | (pred["median"] > pred.upper)).any():
        raise ValueError("Forecast quantiles must be ordered")


def rolling_origin_backtest(
    series: pd.Series,
    make_forecaster: Callable[[], Forecaster],
    cfg: BacktestConfig,
) -> pd.DataFrame:
    """Refit on local calendar days; target labels never enter prediction inputs.

    Every issue returns all model horizons, including end-of-test rows whose
    labels are NaN. Labels outside the configured test interval are not scored.
    """
    validate_series(series)
    issues = _issue_times(cfg)
    if not len(issues):
        raise ValueError("No issue times in the requested test interval")
    frames = []
    forecaster: Forecaster | None = None
    next_refit: date | None = None
    for issue in issues:
        local_date = issue.tz_convert(cfg.tz).date()
        if forecaster is None or next_refit is None or local_date >= next_refit:
            logger.info("Refitting at %s", issue.isoformat())
            forecaster = make_forecaster()
            forecaster.fit(series.loc[:issue].copy(), issue)
            next_refit = local_date + timedelta(days=cfg.retrain_every_days)
        pred = forecaster.predict(series.loc[:issue].copy(), issue).copy()
        _validate_prediction(pred, issue)
        pred.insert(0, "issue_time", issue)
        pred["y"] = series.reindex(pd.DatetimeIndex(pred.target_time)).to_numpy()
        pred.loc[pred.target_time > cfg.test_end, "y"] = np.nan
        frames.append(pred[BACKTEST_COLUMNS])
    return pd.concat(frames, ignore_index=True)
