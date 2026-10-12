"""Deterministic global quantile models and the forecaster adapter."""

from collections.abc import Mapping, Sequence
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from carbon_scheduler.features.build import FEATURE_COLUMNS, build_supervised
from carbon_scheduler.models.base import utc_hour, validate_series

QUANTILES = (0.1, 0.5, 0.9)
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "verbose": -1,
}


class QuantileLgbm:
    def __init__(
        self,
        alphas: Sequence[float] = QUANTILES,
        params: Mapping[str, Any] | None = None,
        seed: int = 42,
        columns: Sequence[str] = FEATURE_COLUMNS,
    ) -> None:
        if tuple(alphas) != QUANTILES:
            raise ValueError("Supported quantiles are exactly (0.1, 0.5, 0.9)")
        self.alphas = tuple(alphas)
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.seed = seed
        self.models_: list[Any] = []
        self.feature_columns_ = list(columns)

    def _features(self, X: pd.DataFrame) -> pd.DataFrame:
        columns = getattr(self, "feature_columns_", FEATURE_COLUMNS)
        missing = set(columns) - set(X.columns)
        if missing:
            raise ValueError(f"Missing feature columns: {', '.join(sorted(missing))}")
        values = X[columns].astype("float64")
        if np.isinf(values.to_numpy()).any():
            raise ValueError("Features must be finite or NaN")
        return values

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "QuantileLgbm":
        features = self._features(X)
        target = y.to_numpy(dtype=float, na_value=np.nan)
        if not len(features) or len(features) != len(target) or not np.isfinite(target).all():
            raise ValueError("Need nonempty aligned finite training targets")
        models = []
        for alpha in self.alphas:
            model = LGBMRegressor(
                **{
                    **self.params,
                    "objective": "quantile",
                    "alpha": alpha,
                    "random_state": self.seed,
                    "n_jobs": 1,
                    "deterministic": True,
                    "force_col_wise": True,
                }
            )
            model.fit(features, target)
            models.append(model)
        self.models_ = models
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        if len(self.models_) != len(QUANTILES):
            raise RuntimeError("Call fit before predict")
        features = self._features(X)
        values = np.column_stack([model.predict(features) for model in self.models_])
        return pd.DataFrame(np.sort(values, axis=1), columns=["q10", "q50", "q90"], index=X.index)


class LgbmForecaster:
    def __init__(
        self,
        tz: str,
        alphas: Sequence[float] = QUANTILES,
        issue_step_h: int = 3,
        seed: int = 42,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        ZoneInfo(tz)
        if isinstance(issue_step_h, bool) or not isinstance(issue_step_h, int) or issue_step_h < 1:
            raise ValueError("issue_step_h must be a positive integer")
        self.tz = tz
        self.issue_step_h = issue_step_h
        self.model = QuantileLgbm(alphas, params, seed)
        self.fit_end_: pd.Timestamp | None = None
        self.n_train_ = 0

    def fit(self, series: pd.Series, fit_end: pd.Timestamp) -> None:
        validate_series(series)
        end = utc_hour(fit_end)
        history = series.loc[:end]
        frame = build_supervised(
            history, pd.DatetimeIndex(history.index[:: self.issue_step_h]), tz=self.tz
        )
        frame = frame.loc[(frame.target_time <= end) & np.isfinite(frame.y)].copy()
        if frame.empty:
            raise ValueError("No finite training targets at or before fit_end")
        self.model.fit(frame, frame.y)
        self.fit_end_ = end
        self.n_train_ = len(frame)

    def predict(self, series: pd.Series, issue_time: pd.Timestamp) -> pd.DataFrame:
        if self.fit_end_ is None:
            raise RuntimeError("Call fit before predict")
        issue = utc_hour(issue_time)
        if issue < self.fit_end_:
            raise ValueError("issue_time cannot precede fit_end")
        frame = build_supervised(
            series.loc[:issue],
            pd.DatetimeIndex([issue]),
            tz=self.tz,
            with_target=False,
        )
        quantiles = self.model.predict(frame)
        result = frame[["target_time", "horizon"]].copy()
        result[["lower", "median", "upper"]] = quantiles.to_numpy()
        return result
