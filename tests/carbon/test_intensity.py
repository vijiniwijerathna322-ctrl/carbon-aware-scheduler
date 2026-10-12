import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.carbon.factors import EmissionFactors, UnknownFuelError
from carbon_scheduler.carbon.intensity import compute_intensity

COAL_FACTOR = 820.0
SOLAR_FACTOR = 48.0
CHANGED_FACTOR = 123.0


@pytest.fixture
def factors():
    return EmissionFactors({"col": 820.0, "sun": 48.0}, frozenset({"bat", "unk"}), "Study")


def compute(df, factors):
    return compute_intensity(df, factors)


@pytest.mark.parametrize("coal,solar,expected", [(10, 0, 820.0), (5, 5, 434.0)])
def test_generation_weighted_intensity(factors, coal, solar, expected):
    result = compute(pd.DataFrame({"gen_col_mwh": [coal], "gen_sun_mwh": [solar]}), factors)
    assert result.iloc[0] == expected


def test_storage_and_unknown_are_explicitly_excluded(factors):
    df = pd.DataFrame({"gen_col_mwh": [1], "gen_bat_mwh": [999], "gen_unk_mwh": [999]})
    assert compute(df, factors).iloc[0] == COAL_FACTOR


def test_zero_and_all_missing_are_nan(factors):
    df = pd.DataFrame({"gen_col_mwh": [0, np.nan], "gen_sun_mwh": [0, np.nan]})
    assert compute(df, factors).isna().all()


def test_negative_generation_is_clipped_without_mutation(factors):
    df = pd.DataFrame({"gen_col_mwh": [-10, -10], "gen_sun_mwh": [5, -5]})
    original = df.copy(deep=True)
    result = compute(df, factors)
    assert result.iloc[0] == SOLAR_FACTOR
    assert pd.isna(result.iloc[1])
    pd.testing.assert_frame_equal(df, original)


def test_random_positive_mix_is_bounded_by_factors(factors):
    rng = np.random.default_rng(42)
    df = pd.DataFrame(rng.uniform(0, 100, (100, 2)), columns=["gen_col_mwh", "gen_sun_mwh"])
    assert compute(df, factors).between(48, 820).all()


def test_changing_factor_changes_output(factors):
    df = pd.DataFrame({"gen_col_mwh": [1]})
    changed = EmissionFactors({"col": 123.0}, frozenset(), "Other study")
    assert compute(df, factors).iloc[0] == COAL_FACTOR
    assert compute(df, changed).iloc[0] == CHANGED_FACTOR


def test_unknown_fuel_is_reported_even_when_missing(factors):
    with pytest.raises(UnknownFuelError, match="newfuel"):
        compute(pd.DataFrame({"gen_newfuel_mwh": [np.nan]}), factors)


def test_partial_missing_uses_observed_mix_without_imputation(factors):
    df = pd.DataFrame({"gen_col_mwh": [np.nan, 2], "gen_sun_mwh": [3, np.nan]})
    original = df.copy(deep=True)
    assert compute(df, factors).tolist() == [48.0, 820.0]
    pd.testing.assert_frame_equal(df, original)


@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame({"gen_bat_mwh": [1, 2]}, index=["b", "a"]),
        pd.DataFrame({"ordinary": ["ignored", "text"]}, index=["b", "a"]),
        pd.DataFrame({"gen_col_mwh": pd.Series(dtype="float64")}),
        pd.DataFrame(),
    ],
)
def test_no_included_generation_preserves_typed_nan_series(factors, df):
    expected = pd.Series(np.nan, index=df.index, dtype="float64", name="carbon_intensity_g_per_kwh")
    pd.testing.assert_series_equal(compute(df, factors), expected)


@pytest.mark.parametrize("column", ["gen_col_mwh", "gen_bat_mwh"])
@pytest.mark.parametrize("value", [np.inf, -np.inf, "invalid", "12", True])
def test_invalid_generation_is_rejected_in_included_and_excluded_fuels(factors, column, value):
    with pytest.raises(ValueError, match=column):
        compute(pd.DataFrame({column: [value]}), factors)


def test_index_order_duplicates_and_input_are_preserved(factors):
    df = pd.DataFrame({"gen_col_mwh": [2, 1, 3], "note": ["a", "b", "c"]}, index=[4, 2, 4])
    df.index.name = "interval"
    original = df.copy(deep=True)
    expected = pd.Series(820.0, index=df.index, name="carbon_intensity_g_per_kwh")
    pd.testing.assert_series_equal(compute(df, factors), expected)
    pd.testing.assert_frame_equal(df, original)
