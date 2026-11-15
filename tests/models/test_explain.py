"""Per-forecast feature attribution via LightGBM's native TreeSHAP contributions."""

# ruff: noqa: PLR2004

import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.explain import explain_forecast
from carbon_scheduler.models.forecast_model import ForecastModel


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(7)
    hours = np.arange(200 * 24)
    series = pd.Series(
        100 + 30 * np.sin(2 * np.pi * hours / 24) + rng.normal(0, 1, len(hours)),
        index=pd.date_range("2024-01-01", periods=len(hours), freq="h", tz="UTC"),
    )
    end = series.index[180 * 24]
    model = ForecastModel("demand_mwh", "UTC", lgbm_params={"n_estimators": 60})
    model.fit(series, end)
    return model, series, end


def test_contributions_reconstruct_the_raw_median(fitted):
    model, series, end = fitted
    frame = model._feature_frame(series, end)
    raw_q50 = model.model.predict(frame)["q50"].to_numpy()
    results = explain_forecast(model, series, end, top_n=3)
    assert len(results) == 48
    reconstructed = np.array([result.raw_median for result in results])
    assert np.allclose(reconstructed, raw_q50, atol=1e-6)


def test_contributions_are_ranked_and_truncated(fitted):
    model, series, end = fitted
    for result in explain_forecast(model, series, end, top_n=3):
        assert len(result.contributions) == 3
        magnitudes = [abs(c.contribution) for c in result.contributions]
        assert magnitudes == sorted(magnitudes, reverse=True)


def test_strong_daily_signal_feature_often_dominates(fitted):
    model, series, end = fitted
    results = explain_forecast(model, series, end, top_n=1)
    daily_signal_features = {"anchor_24", "y_lag24", "hour_local", "roll_mean_24"}
    top_features = [result.contributions[0].feature for result in results]
    assert (
        sum(feature in daily_signal_features for feature in top_features) >= len(top_features) // 2
    )


def test_horizon_filter_returns_a_single_point(fitted):
    model, series, end = fitted
    results = explain_forecast(model, series, end, horizon=5)
    assert len(results) == 1
    assert results[0].horizon == 5
