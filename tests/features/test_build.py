# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.features.build import FEATURE_COLUMNS, build_supervised


@pytest.fixture
def series():
    return pd.Series(
        np.arange(400.0), index=pd.date_range("2024-03-01", periods=400, freq="h", tz="UTC")
    )


def test_future_perturbation_cannot_change_features(series):
    issue = pd.DatetimeIndex([series.index[250]])
    before = build_supervised(series, issue, tz="America/Los_Angeles")
    changed = series.copy()
    changed.loc[changed.index > issue[0]] += 1e6
    after = build_supervised(changed, issue, tz="America/Los_Angeles")
    pd.testing.assert_frame_equal(before[FEATURE_COLUMNS], after[FEATURE_COLUMNS])
    assert (before.y != after.y).all()


def test_anchor_target_and_issue_definitions(series):
    frame = build_supervised(
        series, pd.DatetimeIndex([series.index[250]]), tz="UTC", horizons=(5, 30)
    )
    assert frame.anchor_24.tolist() == [231.0, 232.0]
    assert frame.anchor_168.tolist() == [87.0, 112.0]
    assert frame.y.tolist() == [255.0, 280.0]
    assert frame.y_issue.tolist() == [250.0, 250.0]
    assert frame.y_lag1.tolist() == [249.0, 249.0]
    assert frame.y_lag24.tolist() == [226.0, 226.0]
    assert frame.roll_mean_24.iloc[0] == pytest.approx(np.arange(227, 251).mean())


@pytest.mark.parametrize("date", ["2024-03-10T08:00Z", "2024-11-03T07:00Z"])
def test_dst_target_calendar_is_local_and_preserves_utc(date):
    data = pd.Series(
        np.ones(500),
        index=pd.date_range(pd.Timestamp(date) - pd.Timedelta(days=10), periods=500, freq="h"),
    )
    issues = pd.DatetimeIndex([pd.Timestamp(date)])
    frame = build_supervised(data, issues, tz="America/Los_Angeles")
    expected = frame.target_time.dt.tz_convert("America/Los_Angeles").dt.hour
    pd.testing.assert_series_equal(frame.hour_local, expected, check_names=False)
    assert len(frame) == 48
    assert str(frame.target_time.dt.tz) == "UTC"


def test_missing_targets_and_features_stay_missing(series):
    series.iloc[249] = np.nan
    frame = build_supervised(
        series, pd.DatetimeIndex([series.index[250], series.index[-1]]), tz="UTC", with_target=False
    )
    assert len(frame) == 96
    assert frame.y.isna().all()
    assert frame.iloc[0].y_lag1 != frame.iloc[0].y_lag1
    assert pd.isna(frame.iloc[0].roll_mean_24)


def test_empty_issues_and_holiday(series):
    empty = build_supervised(series, pd.DatetimeIndex([], tz="UTC"), tz="UTC")
    assert empty.empty
    holiday = build_supervised(
        series, pd.DatetimeIndex([pd.Timestamp("2024-07-04T00Z")]), tz="UTC", horizons=(1,)
    )
    assert holiday.is_us_holiday.iloc[0] == 1


def test_invalid_series_and_issues_raise(series):
    with pytest.raises(ValueError, match="UTC"):
        build_supervised(series.tz_localize(None), pd.DatetimeIndex([series.index[250]]), tz="UTC")
    with pytest.raises(ValueError, match="hour"):
        build_supervised(
            series, pd.DatetimeIndex([series.index[250] + pd.Timedelta(minutes=1)]), tz="UTC"
        )
