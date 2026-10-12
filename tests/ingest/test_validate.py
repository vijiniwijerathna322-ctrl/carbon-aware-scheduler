# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.ingest.validate import validate_and_clean


def frame(n: int = 400) -> pd.DataFrame:
    values = 100 + 10 * np.sin(np.arange(n) * 2 * np.pi / 24)
    return pd.DataFrame(
        {
            name: values.copy()
            for name in (
                "demand_mwh",
                "demand_forecast_mwh",
                "net_generation_mwh",
                "net_interchange_mwh",
            )
        },
        index=pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC"),
    )


def test_clean_data_unchanged_and_input_not_mutated() -> None:
    original = frame()
    cleaned, report = validate_and_clean(original)
    pd.testing.assert_frame_equal(cleaned, original)
    assert cleaned is not original
    assert report.n_rows == 400
    assert report.n_spikes == report.n_interpolated == report.n_remaining_gaps == 0


def test_negative_demand_and_spikes_counted_without_overlap() -> None:
    data = frame()
    data.iloc[100, 0] = -1
    data.iloc[200, 0] *= 10
    data.iloc[200, 2] *= 10
    original = data.copy(deep=True)
    cleaned, report = validate_and_clean(data)
    assert report.n_negative_demand == 1
    assert report.n_spikes == 2
    assert report.n_interpolated == 3
    assert cleaned.notna().all().all()
    pd.testing.assert_frame_equal(data, original)


def test_complete_short_runs_only_and_cell_counts() -> None:
    data = frame()
    data.iloc[:2, 0] = np.nan
    data.iloc[20:22, :2] = np.nan
    data.iloc[40:45, 0] = np.nan
    data.iloc[-1, 0] = 0
    cleaned, report = validate_and_clean(data)
    assert cleaned.iloc[20:22, :2].notna().all().all()
    assert cleaned.iloc[40:45, 0].isna().all()
    assert report.n_interpolated == 4
    assert report.n_remaining_gaps == 8
    assert report.n_remaining_missing_cells == 8
    assert report.gap_fraction == 8 / 400


def test_constant_mad_isolated_spike() -> None:
    data = frame()
    data["demand_mwh"] = 100.0
    data.iloc[200, 0] = 1000
    cleaned, report = validate_and_clean(data)
    assert report.n_spikes == 1
    assert cleaned.iloc[200, 0] == 100


def test_missing_core_and_late_fuel_diagnostics() -> None:
    data = frame().drop(columns="demand_forecast_mwh")
    data["gen_geo_mwh"] = np.nan
    data.iloc[300:, -1] = 5.0
    data.iloc[350:355, -1] = np.nan
    cleaned, report = validate_and_clean(data)
    assert report.n_remaining_gaps == 400
    assert report.gap_fraction == 1
    assert report.missing_by_column["demand_forecast_mwh"] == 400
    assert report.missing_by_column["gen_geo_mwh"] == 305
    assert report.n_remaining_missing_cells == 705
    assert report.first_observed_by_column["gen_geo_mwh"] == data.index[300].isoformat()
    assert report.last_observed_by_column["gen_geo_mwh"] == data.index[-1].isoformat()
    assert report.interior_missing_by_column["gen_geo_mwh"] == 5
    assert cleaned["gen_geo_mwh"].iloc[:300].isna().all()
    assert report.n_duplicates == 0


@pytest.mark.parametrize("kind", ["naive", "irregular", "infinity"])
def test_invalid_contract_rejected(kind: str) -> None:
    data = frame()
    if kind == "naive":
        data.index = data.index.tz_localize(None)
    elif kind == "irregular":
        data = data.drop(data.index[5])
    else:
        data.iloc[5, 0] = np.inf
    with pytest.raises(ValueError):
        validate_and_clean(data)


def test_empty_frame_and_disabled_interpolation() -> None:
    cleaned, report = validate_and_clean(frame(0))
    assert cleaned.empty
    assert report.gap_fraction == 0
    assert report.first_observed_by_column["demand_mwh"] is None
    data = frame()
    data.iloc[10, 0] = np.nan
    cleaned, report = validate_and_clean(data, max_gap_hours=0)
    assert pd.isna(cleaned.iloc[10, 0])
    assert report.n_interpolated == 0


@pytest.mark.parametrize("options", [{"spike_z": 0}, {"max_gap_hours": -1}])
def test_invalid_options_rejected(options: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        validate_and_clean(frame(), **options)
