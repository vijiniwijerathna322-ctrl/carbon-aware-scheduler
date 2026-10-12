"""Weekly seasonal-naive point forecasts."""

from collections.abc import Sequence

import numpy as np
import pandas as pd

from carbon_scheduler.models.base import HORIZONS, utc_hour, validate_horizons, validate_series


class SeasonalNaiveForecaster:
    def __init__(self, season_h: int = 168, horizons: Sequence[int] = HORIZONS) -> None:
        self.horizons = validate_horizons(horizons)
        if (
            isinstance(season_h, bool)
            or not isinstance(season_h, int)
            or season_h < max(self.horizons)
        ):
            raise ValueError("season_h must cover every requested horizon")
        self.season_h = season_h

    def fit(self, series: pd.Series, fit_end: pd.Timestamp) -> None:
        validate_series(series)
        utc_hour(fit_end)

    def predict(self, series: pd.Series, issue_time: pd.Timestamp) -> pd.DataFrame:
        validate_series(series)
        issue = utc_hour(issue_time)
        targets = issue + pd.to_timedelta(self.horizons, unit="h")
        history = series.loc[:issue]
        return pd.DataFrame(
            {
                "target_time": targets,
                "horizon": self.horizons,
                "lower": np.nan,
                "median": history.reindex(targets - pd.Timedelta(hours=self.season_h)).to_numpy(),
                "upper": np.nan,
            }
        )
