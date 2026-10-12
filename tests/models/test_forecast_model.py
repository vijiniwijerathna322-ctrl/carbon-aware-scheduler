# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.lgbm import QuantileLgbm


@pytest.fixture(scope="module")
def history():
    rng = np.random.default_rng(3)
    hours = np.arange(200 * 24)
    return pd.Series(
        100 + 20 * np.sin(2 * np.pi * hours / 24) + rng.normal(0, 4, len(hours)),
        index=pd.date_range("2024-01-01", periods=len(hours), freq="h", tz="UTC"),
    )


def test_training_calibration_boundaries_and_ordered_predictions(history, monkeypatch):
    seen = []
    original = QuantileLgbm.fit

    def spy(self, X, y):
        seen.append(X.copy())
        return original(self, X, y)

    monkeypatch.setattr(QuantileLgbm, "fit", spy)
    end = history.index[180 * 24]
    model = ForecastModel("demand_mwh", "UTC", lgbm_params={"n_estimators": 40})
    model.fit(history, end)
    assert seen[0].target_time.max() <= end - pd.Timedelta(days=90)
    assert model.calibration_predictions_.issue_time.min() > end - pd.Timedelta(days=90)
    assert model.calibration_predictions_.target_time.max() <= end
    assert model.metadata()["n_calibration"] > 0
    result = model.predict(history, end)
    assert len(result) == 48
    assert (result.lower <= result["median"]).all()
    assert (result["median"] <= result.upper).all()
    dirty = history.copy()
    dirty.loc[dirty.index > end] = 1e9
    pd.testing.assert_frame_equal(result, model.predict(dirty, end))


def test_synthetic_holdout_coverage_and_metadata(history):
    end = history.index[180 * 24]
    model = ForecastModel("demand_mwh", "UTC", lgbm_params={"n_estimators": 40})
    model.fit(history, end)
    frames = [model.predict(history, issue) for issue in history.index[181 * 24 : 198 * 24 : 24]]
    pred = pd.concat(frames, ignore_index=True)
    actual = history.reindex(pd.DatetimeIndex(pred.target_time)).to_numpy()
    coverage = np.mean((actual >= pred.lower) & (actual <= pred.upper))
    assert 0.75 <= coverage <= 0.85
    for key in (
        "target",
        "tz",
        "alpha",
        "train_end",
        "calibration_start",
        "fit_end",
        "n_train",
        "n_calibration",
        "feature_columns",
        "corrections",
        "data_start",
        "data_end",
    ):
        assert key in model.metadata()


def test_short_history_and_unfitted_raise(history):
    model = ForecastModel("demand_mwh", "UTC")
    with pytest.raises(ValueError, match="30 days"):
        model.fit(history.iloc[: 100 * 24], history.index[99 * 24])
    with pytest.raises(RuntimeError, match="fit"):
        model.predict(history, history.index[-1])
