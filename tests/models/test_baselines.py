# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.baselines import SeasonalNaiveForecaster


def series():
    return pd.Series(
        np.arange(400.0), index=pd.date_range("2024-01-01", periods=400, freq="h", tz="UTC")
    )


def test_uses_weekly_anchor_without_future_read():
    data = series()
    issue = data.index[300]
    model = SeasonalNaiveForecaster()
    model.fit(data.loc[:issue], issue)
    pred = model.predict(data.loc[:issue], issue)
    assert len(pred) == 48
    np.testing.assert_array_equal(pred["median"], np.arange(133.0, 181.0))
    assert pred["lower"].isna().all()
    assert pred["upper"].isna().all()
    pd.testing.assert_frame_equal(pred, model.predict(data, issue))


def test_horizon_beyond_season_raises():
    with pytest.raises(ValueError, match="season"):
        SeasonalNaiveForecaster(season_h=24)
    with pytest.raises(ValueError, match="horizon"):
        SeasonalNaiveForecaster(horizons=(0,))


def test_missing_anchor_keeps_prediction_row():
    data = series()
    pred = SeasonalNaiveForecaster(horizons=(1, 2)).predict(data.iloc[:2], data.index[1])
    assert pred["median"].isna().all()
    assert len(pred) == 2
