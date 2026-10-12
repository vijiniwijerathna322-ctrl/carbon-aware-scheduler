"""Provider contract, strict missingness and forecast cache expiration."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.regions import WeatherPoint
from carbon_scheduler.weather.client import VARIABLES, WeatherClient, WeatherUnavailable


def payload():
    return json.loads(Path("tests/fixtures/open_meteo/archive.json").read_text(encoding="utf-8"))


def test_history_cache_and_weighted_mean(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        data = payload()
        value = 10.0 if request.url.params["latitude"] == "1" else 30.0
        data["hourly"]["temperature_2m"] = [value] * 48
        return httpx.Response(200, json=data)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = WeatherClient(tmp_path, http)
        points = (WeatherPoint(1, 1, 3), WeatherPoint(2, 2, 1))
        first = client.fetch_history(points, date(2021, 1, 1), date(2021, 1, 2))
        second = client.fetch_history(points, date(2021, 1, 1), date(2021, 1, 2))
    assert len(calls) == 2  # noqa: PLR2004
    assert list(first) == list(VARIABLES)
    assert str(first.index.tz) == "UTC"
    assert first.temperature_2m.eq(15.0).all()
    pd.testing.assert_frame_equal(first, second)


def test_forecast_ttl_and_http_error(tmp_path):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = WeatherClient(tmp_path, http, clock=lambda: now)
        points = [WeatherPoint(1, 1, 1)]
        client.fetch_forecast(points, 48)
        now += timedelta(minutes=59)
        client.fetch_forecast(points, 48)
        assert len(calls) == 1
        now += timedelta(minutes=1)
        client.fetch_forecast(points, 48)
        assert len(calls) == 2  # noqa: PLR2004
        assert calls[-1].url.params["forecast_hours"] == "48"
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as http,
        pytest.raises(WeatherUnavailable),
    ):
        WeatherClient(tmp_path / "missing", http).fetch_forecast(points)


def test_missing_point_is_not_renormalized(tmp_path):
    def handler(request):
        data = payload()
        if request.url.params["latitude"] == "2":
            data["hourly"]["temperature_2m"][0] = None
        return httpx.Response(200, json=data)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        frame = WeatherClient(tmp_path, http).fetch_history(
            [WeatherPoint(1, 1, 1), WeatherPoint(2, 2, 1)], date(2021, 1, 1), date(2021, 1, 2)
        )
    assert np.isnan(frame.temperature_2m.iloc[0])
    assert frame.attrs["missing_cells"] == 1


def test_explicit_forecast_range_covers_next_48_target_hours(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload())

    issue = pd.Timestamp("2020-12-31T23:00Z")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        frame = WeatherClient(tmp_path, http).fetch_forecast(
            [WeatherPoint(1, 1, 1)], issue_time=issue
        )
    assert frame.index.equals(pd.date_range(issue + pd.Timedelta(hours=1), periods=48, freq="h"))
    assert calls[0].url.params["start_hour"] == "2021-01-01T00:00"
    assert calls[0].url.params["end_hour"] == "2021-01-02T23:00"
    assert "forecast_days" not in calls[0].url.params


@pytest.mark.parametrize("fault", ["units", "timezone", "duplicate", "infinity"])
def test_invalid_provider_contract_is_rejected(tmp_path, fault):
    data = payload()
    if fault == "units":
        data["hourly_units"]["wind_speed_100m"] = "m/s"
    elif fault == "timezone":
        data["utc_offset_seconds"] = 3600
    elif fault == "duplicate":
        data["hourly"]["time"][1] = data["hourly"]["time"][0]
    else:
        data["hourly"]["temperature_2m"][0] = float("inf")
    # JSON itself cannot represent infinity, so inject it through decoded response.
    response = httpx.Response(200, json=payload())
    response.json = lambda: data
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: response)) as http,
        pytest.raises(WeatherUnavailable),
    ):
        WeatherClient(tmp_path, http).fetch_forecast([WeatherPoint(1, 1, 1)])
