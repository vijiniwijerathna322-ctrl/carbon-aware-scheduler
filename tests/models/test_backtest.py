# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.backtest import BacktestConfig, rolling_origin_backtest
from carbon_scheduler.models.baselines import SeasonalNaiveForecaster
from carbon_scheduler.models.metrics import mae


def history():
    return pd.Series(
        np.arange(100 * 24) % 168,
        index=pd.date_range("2024-01-01", periods=100 * 24, freq="h", tz="UTC"),
    )


def test_physical_truncation_refit_cadence_and_rows():
    data = history()
    fits, predictions = [], []

    class Spy(SeasonalNaiveForecaster):
        def fit(self, series, fit_end):
            fits.append((series.index.max(), fit_end))

        def predict(self, series, issue_time):
            predictions.append((series.index.max(), issue_time))
            return super().predict(series, issue_time)

    start = pd.Timestamp("2024-02-01T00Z")
    cfg = BacktestConfig(start, start + pd.Timedelta(days=60) - pd.Timedelta(hours=1), "UTC")
    result = rolling_origin_backtest(data, Spy, cfg)
    assert len(fits) == 2
    assert len(predictions) == 60
    assert len(result) == 60 * 48
    assert all(latest <= cutoff for latest, cutoff in fits + predictions)
    assert mae(result.y, result["median"]) == 0
    assert result.loc[result.target_time > cfg.test_end, "y"].isna().all()


@pytest.mark.parametrize("start", ["2024-03-08T08Z", "2024-11-01T07Z"])
def test_local_midnight_is_preserved_across_dst(start):
    beginning = pd.Timestamp(start)
    data = pd.Series(
        np.ones(500), index=pd.date_range(beginning - pd.Timedelta(days=10), periods=500, freq="h")
    )
    cfg = BacktestConfig(beginning, beginning + pd.Timedelta(days=5), "America/Los_Angeles")
    result = rolling_origin_backtest(data, SeasonalNaiveForecaster, cfg)
    local = pd.DatetimeIndex(result.issue_time.unique()).tz_convert(cfg.tz)
    assert (local.hour == 0).all()
    assert len(local) == len(set(local.date))


def test_invalid_configuration_and_empty_test_raise():
    with pytest.raises(ValueError, match="retrain"):
        BacktestConfig(
            pd.Timestamp("2024-01-01T00Z"),
            pd.Timestamp("2024-02-01T00Z"),
            "UTC",
            retrain_every_days=0,
        )
    with pytest.raises(ValueError, match="issue"):
        rolling_origin_backtest(
            history(),
            SeasonalNaiveForecaster,
            BacktestConfig(
                pd.Timestamp("2025-01-01T00Z"),
                pd.Timestamp("2025-01-01T00Z"),
                "UTC",
                issue_hour_local=1,
            ),
        )
