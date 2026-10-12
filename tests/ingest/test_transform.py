import pandas as pd
import pytest

from carbon_scheduler.ingest.transform import to_hourly_frame

CORE = ["demand_mwh", "demand_forecast_mwh", "net_generation_mwh", "net_interchange_mwh"]


def frame(category, rows=()):
    result = pd.DataFrame(rows, columns=["period", category, "value"])
    result["period"] = pd.to_datetime(result["period"], utc=True).astype("datetime64[ns, UTC]")
    result[category] = result[category].astype("str")
    result["value"] = result["value"].astype("float64")
    return result


def test_pivots_types_to_columns():
    region = frame(
        "type",
        [
            ("2024-01-01T00", code, value)
            for code, value in zip(["D", "DF", "NG", "TI"], [1, 2, 3, -4], strict=True)
        ],
    )
    fuel = frame("fueltype", [("2024-01-01T00", "SUN", 5), ("2024-01-01T00", "COL", 6)])
    result, count = to_hourly_frame(region, fuel)
    assert list(result) == CORE + ["gen_col_mwh", "gen_sun_mwh"]
    assert result.iloc[0].tolist() == [1, 2, 3, -4, 6, 5]
    assert all(dtype == "float64" for dtype in result.dtypes)
    assert count == 0


def test_duplicates_keep_last_and_are_counted():
    latest_demand = 2
    expected_duplicates = 2
    result, count = to_hourly_frame(
        frame("type", [("2024-01-01T00", "D", 1), ("2024-01-01T00", "D", 2)]),
        frame("fueltype", [("2024-01-01T00", "SUN", 3), ("2024-01-01T00", "SUN", None)]),
    )
    assert result.iloc[0]["demand_mwh"] == latest_demand
    assert pd.isna(result.iloc[0]["gen_sun_mwh"])
    assert count == expected_duplicates


def test_last_null_region_revision_is_preserved():
    result, count = to_hourly_frame(
        frame("type", [("2024-01-01T00", "D", 1), ("2024-01-01T00", "D", None)]),
        frame("fueltype"),
    )
    assert result.iloc[0].isna().all()
    assert count == 1


def test_index_is_complete_hourly_utc():
    result, _ = to_hourly_frame(
        frame("type", [("2024-01-01T00", "D", 1)]),
        frame("fueltype", [("2024-01-01T02", "WND", 2)]),
    )
    expected = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC", name="period").astype(
        "datetime64[ns, UTC]"
    )
    pd.testing.assert_index_equal(result.index, expected)
    assert result.iloc[1].isna().all()


def test_unknown_type_ignored_not_crash():
    result, _ = to_hourly_frame(frame("type", [("2024-01-01T00", "OTHER", 100)]), frame("fueltype"))
    assert list(result) == CORE
    assert len(result) == 1
    assert result.isna().all().all()


@pytest.mark.parametrize("fuel_only", [False, True])
def test_empty_and_fuel_only_have_stable_schema(fuel_only):
    fuel = frame("fueltype", [("2024-01-01T00", "NEW", 7)] if fuel_only else [])
    result, count = to_hourly_frame(frame("type"), fuel)
    assert list(result) == CORE + (["gen_new_mwh"] if fuel_only else [])
    assert str(result.index.dtype) == "datetime64[ns, UTC]"
    assert result.index.name == "period"
    assert len(result) == int(fuel_only)
    assert all(dtype == "float64" for dtype in result.dtypes)
    assert count == 0


def test_inputs_are_not_mutated():
    region = frame("type", [("2024-01-01T00", "D", 1)])
    fuel = frame("fueltype", [("2024-01-01T00", "SUN", 2)])
    original_region, original_fuel = region.copy(deep=True), fuel.copy(deep=True)
    to_hourly_frame(region, fuel)
    pd.testing.assert_frame_equal(region, original_region)
    pd.testing.assert_frame_equal(fuel, original_fuel)


@pytest.mark.parametrize("invalid", ["naive", "off_hour", "missing"])
def test_invalid_period_rejected(invalid):
    region = frame("type", [("2024-01-01T00", "D", 1)])
    if invalid == "naive":
        region["period"] = region["period"].dt.tz_localize(None)
    elif invalid == "off_hour":
        region["period"] += pd.Timedelta(minutes=1)
    else:
        region.loc[0, "period"] = pd.NaT
    with pytest.raises(ValueError, match="UTC|hour"):
        to_hourly_frame(region, frame("fueltype"))
