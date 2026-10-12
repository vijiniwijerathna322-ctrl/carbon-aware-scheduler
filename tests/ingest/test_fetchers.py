import json
from pathlib import Path

import pandas as pd
import pytest

from carbon_scheduler.ingest.fetchers import fetch_fuel_type_data, fetch_region_data


class StubClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def fetch_route(self, route, **kwargs):
        self.calls.append((route, kwargs))
        return self.rows


@pytest.mark.parametrize(
    ("fetcher", "fixture", "category", "route"),
    [
        (fetch_region_data, "region_data_page.json", "type", "electricity/rto/region-data"),
        (
            fetch_fuel_type_data,
            "fuel_type_data_page.json",
            "fueltype",
            "electricity/rto/fuel-type-data",
        ),
    ],
)
def test_recorded_data_parses_utc_and_numeric(fetcher, fixture, category, route):
    rows = json.loads((Path("tests/fixtures/eia") / fixture).read_text())["response"]["data"]
    client = StubClient(rows)
    result = fetcher(client, "CISO", "2024-01-01T00", "2024-01-02T00")
    assert list(result.columns) == ["period", category, "value"]
    assert str(result.period.dtype) == "datetime64[ns, UTC]"
    assert str(result.value.dtype) == "float64"
    assert result.period.iloc[0] == pd.Timestamp(rows[0]["period"], tz="UTC")
    assert result.value.iloc[0] == float(rows[0]["value"])
    assert client.calls == [
        (
            route,
            {"facets": {"respondent": ["CISO"]}, "start": "2024-01-01T00", "end": "2024-01-02T00"},
        )
    ]


@pytest.mark.parametrize(
    ("fetcher", "category"), [(fetch_region_data, "type"), (fetch_fuel_type_data, "fueltype")]
)
@pytest.mark.parametrize("value", [None, "not available", ""])
def test_null_or_invalid_value_becomes_nan(fetcher, category, value):
    result = fetcher(
        StubClient([{"period": "2024-01-01T00", category: "NG", "value": value}]),
        "CISO",
        "start",
        "end",
    )
    assert pd.isna(result.value.iloc[0])
    assert str(result.value.dtype) == "float64"


@pytest.mark.parametrize(
    ("fetcher", "category"), [(fetch_region_data, "type"), (fetch_fuel_type_data, "fueltype")]
)
def test_empty_response_returns_typed_empty_frame(fetcher, category):
    result = fetcher(StubClient([]), "CISO", "start", "end")
    assert result.empty
    assert list(result.columns) == ["period", category, "value"]
    assert str(result.period.dtype) == "datetime64[ns, UTC]"
    assert str(result.value.dtype) == "float64"


@pytest.mark.parametrize(
    "period", ["2024-01-01T00-08:00", "2024-01-01T00Z", "2024-01-01T00:30", "invalid", None]
)
def test_unverified_period_format_rejected(period):
    with pytest.raises(ValueError, match="period"):
        fetch_region_data(
            StubClient([{"period": period, "type": "D", "value": "1"}]), "CISO", "start", "end"
        )
