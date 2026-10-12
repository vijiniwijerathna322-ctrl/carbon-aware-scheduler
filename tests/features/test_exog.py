"""Target joins preserve missingness and the base feature contract."""

import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.features.build import FEATURE_COLUMNS, build_supervised, feature_columns
from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.registry import load_model, save_model


def test_target_join_and_no_filling():
    index = pd.date_range("2024-01-01", periods=200, freq="h", tz="UTC")
    series = pd.Series(np.arange(len(index)), index=index)
    issue = pd.DatetimeIndex([index[-4]])
    exog = pd.DataFrame({"temperature_2m": [10.0, 20.0]}, index=index[-3:-1])
    original = build_supervised(series, issue, tz="UTC", horizons=(1, 2, 3))
    frame = build_supervised(series, issue, tz="UTC", horizons=(1, 2, 3), exog=exog)
    assert frame.wx_temperature_2m.iloc[:2].tolist() == [10.0, 20.0]
    assert np.isnan(frame.wx_temperature_2m.iloc[-1])
    pd.testing.assert_frame_equal(frame.drop(columns="wx_temperature_2m"), original)
    assert feature_columns(None) == FEATURE_COLUMNS
    assert feature_columns(exog)[-1] == "wx_temperature_2m"
    with pytest.raises(ValueError, match="UTC"):
        build_supervised(series, issue, tz="UTC", exog=exog.tz_localize(None))


def test_weather_model_roundtrip_and_missing_weather_predicts(tmp_path):
    index = pd.date_range("2024-01-01", periods=150 * 24, freq="h", tz="UTC")
    series = pd.Series(100.0 + np.arange(len(index)) % 24, index=index)
    exog = pd.DataFrame({"temperature_2m": np.sin(np.arange(len(index)) / 24)}, index=index)
    exog.attrs["source"] = "archive_exploratory"
    model = ForecastModel("demand_mwh", "UTC", exog=exog, lgbm_params={"n_estimators": 5})
    model.fit(series, index[-1])
    save_model(model, "CISO", tmp_path)
    loaded = load_model("CISO", "demand_mwh", tmp_path)
    assert loaded.metadata()["exog_columns"] == ["temperature_2m"]
    assert loaded.metadata()["exog_source"] == "archive_exploratory"
    future = pd.DataFrame(
        {"temperature_2m": [np.nan] * 48},
        index=pd.date_range(index[-1] + pd.Timedelta(hours=1), periods=48, freq="h"),
    )
    prediction = loaded.predict(series, index[-1], exog=future)
    assert np.isfinite(prediction[["lower", "median", "upper"]]).all().all()
    pd.testing.assert_frame_equal(
        model.predict(series, index[-1]), loaded.predict(series, index[-1])
    )
