"""Chronologically split quantile training and horizon-bucket CQR calibration."""

from collections.abc import Mapping
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from carbon_scheduler.features.build import build_supervised, feature_columns, validate_exog
from carbon_scheduler.models.base import utc_hour, validate_series
from carbon_scheduler.models.conformal import SplitConformalCQR
from carbon_scheduler.models.evaluate import summarize
from carbon_scheduler.models.lgbm import QuantileLgbm


class ForecastModel:
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        target: str,
        tz: str,
        alpha: float = 0.2,
        calibration_days: int = 90,
        lgbm_params: Mapping[str, Any] | None = None,
        seed: int = 42,
        issue_step_h: int = 3,
        exog: pd.DataFrame | None = None,
        exog_source: str | None = None,
    ) -> None:
        if target not in ("demand_mwh", "carbon_intensity_g_per_kwh"):
            raise ValueError("Unsupported forecast target")
        ZoneInfo(tz)
        if alpha != 0.2:  # noqa: PLR2004
            raise ValueError("Fixed base quantiles require alpha=0.2")
        if calibration_days < 1 or issue_step_h < 1:
            raise ValueError("calibration_days and issue_step_h must be positive")
        self.target = target
        self.tz = tz
        self.alpha = alpha
        self.calibration_days = calibration_days
        self.issue_step_h = issue_step_h
        self.seed = seed
        if exog is not None:
            validate_exog(exog)
        self.exog = exog.copy(deep=True) if exog is not None else None
        self.exog_source = exog_source or (
            str(exog.attrs.get("source", "unspecified_exploratory")) if exog is not None else None
        )
        self.model = QuantileLgbm(params=lgbm_params, seed=seed, columns=feature_columns(exog))
        self.calibrator = SplitConformalCQR(alpha)
        self.fit_end_: pd.Timestamp | None = None
        self.calibration_predictions_ = pd.DataFrame()
        self.metadata_: dict[str, Any] = {}

    def _adjusted(self, frame: pd.DataFrame) -> pd.DataFrame:
        quantiles = self.model.predict(frame)
        lo, hi = self.calibrator.adjust(quantiles.q10, quantiles.q90, frame.horizon)
        result = frame[["issue_time", "target_time", "horizon", "y"]].copy()
        # Contraction may exclude the unchanged median. Widen only enough to
        # retain it; this cannot reduce coverage relative to the CQR interval.
        result["lower"] = np.minimum(lo, quantiles.q50.to_numpy())
        result["median"] = quantiles.q50.to_numpy()
        result["upper"] = np.maximum(hi, quantiles.q50.to_numpy())
        return result

    def fit(self, series: pd.Series, fit_end: pd.Timestamp) -> None:
        validate_series(series)
        end = utc_hour(fit_end)
        history = series.loc[:end]
        start = end - pd.Timedelta(days=self.calibration_days)
        if history.empty or start - history.index[0] < pd.Timedelta(days=30):
            raise ValueError(
                "Need at least 30 days of training history before the calibration window"
            )
        issues = pd.DatetimeIndex(history.index[:: self.issue_step_h])
        training_history = history.loc[:start]
        training = build_supervised(
            training_history, issues[issues <= start], tz=self.tz, exog=self.exog
        )
        training = training.loc[(training.target_time <= start) & np.isfinite(training.y)].copy()
        calibration = build_supervised(history, issues[issues > start], tz=self.tz, exog=self.exog)
        calibration = calibration.loc[
            (calibration.target_time <= end) & np.isfinite(calibration.y)
        ].copy()
        if training.empty or calibration.empty:
            raise ValueError("Need finite training and calibration targets in disjoint windows")
        self.model.fit(training, training.y)
        base = self.model.predict(calibration)
        self.calibrator.calibrate(base.q10, base.q90, calibration.y, calibration.horizon)
        self.calibration_predictions_ = self._adjusted(calibration)
        self.fit_end_ = end
        self.metadata_ = {
            "target": self.target,
            "tz": self.tz,
            "alpha": self.alpha,
            "train_end": start.isoformat(),
            "calibration_start": start.isoformat(),
            "calibration_end": end.isoformat(),
            "fit_end": end.isoformat(),
            "data_start": history.index[0].isoformat(),
            "data_end": history.index[-1].isoformat(),
            "n_train": len(training),
            "n_calibration": len(calibration),
            "feature_columns": feature_columns(self.exog),
            "exog_columns": list(self.exog.columns) if self.exog is not None else [],
            "exog_source": self.exog_source,
            "seed": self.seed,
            "issue_step_h": self.issue_step_h,
            "calibration_days": self.calibration_days,
            "lgbm_parameters": self.model.params,
            "corrections": {
                f"{lo}-{hi}": value for (lo, hi), value in self.calibrator.corrections_.items()
            },
        }

    def predict(
        self, series: pd.Series, issue_time: pd.Timestamp, exog: pd.DataFrame | None = None
    ) -> pd.DataFrame:
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
            exog=exog if exog is not None else getattr(self, "exog", None),
        )
        return self._adjusted(frame)[["target_time", "horizon", "lower", "median", "upper"]]

    def metadata(self) -> dict[str, Any]:
        if self.fit_end_ is None:
            raise RuntimeError("Call fit before reading metadata")
        import copy  # noqa: PLC0415

        return copy.deepcopy(self.metadata_)

    def calibration_summary(self) -> pd.DataFrame:
        """Descriptive reused-calibration scores; never a held-out coverage claim."""
        if self.fit_end_ is None:
            raise RuntimeError("Call fit before reading calibration summary")
        return summarize(self.calibration_predictions_, self.alpha)
