import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from carbon_scheduler.carbon.dataset import build_dataset
from carbon_scheduler.cli import app
from carbon_scheduler.config import Settings, get_settings
from carbon_scheduler.ingest.store import write_hourly

NEGATIVE_CELLS = 2
SHA256_LENGTH = 64
REVISED_FACTOR = 200


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, eia_api_key=None)


@pytest.fixture
def frame(settings):
    df = pd.DataFrame(
        {
            "demand_mwh": [100.0, 200.0, 300.0],
            "gen_col_mwh": [5.0, np.nan, -2.0],
            "gen_sun_mwh": [5.0, 3.0, 0.0],
            "gen_bat_mwh": [10.0, -1.0, np.nan],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC", name="period").astype(
            "datetime64[ns, UTC]"
        ),
    )
    write_hourly(df, "CISO", "interim", settings.data_dir)
    return df


def test_build_dataset_adds_intensity_column_and_keeps_index(settings, frame):
    path = build_dataset("CISO", settings)
    output = pd.read_parquet(path)
    pd.testing.assert_frame_equal(output[frame.columns], frame, check_freq=False)
    assert output.carbon_intensity_g_per_kwh.iloc[:2].tolist() == [434.0, 48.0]
    assert pd.isna(output.carbon_intensity_g_per_kwh.iloc[2])
    assert output.carbon_covered_generation_mwh.tolist() == [10.0, 3.0, 0.0]
    assert output.carbon_excluded_generation_mwh.iloc[:2].tolist() == [10.0, 0.0]
    assert output.carbon_observed_coverage_fraction.iloc[:2].tolist() == [0.5, 1.0]
    assert pd.isna(output.carbon_observed_coverage_fraction.iloc[2])
    assert output.carbon_missing_fuel_count.tolist() == [0, 1, 0]
    assert output.carbon_negative_generation_count.tolist() == [0, 1, 1]
    report = json.loads(path.with_name("carbon-quality-report.json").read_text())
    assert report["included_codes"] == ["col", "sun"]
    assert report["excluded_codes"] == ["bat"]
    assert report["quality"]["missing_intensity_hours"] == 1
    assert report["quality"]["missing_included_fuel_cells"] == 1
    assert report["quality"]["negative_generation_cells"] == NEGATIVE_CELLS
    assert report["source"]
    assert len(report["input_sha256"]) == SHA256_LENGTH


def test_build_dataset_missing_interim_gives_actionable_error(settings):
    with pytest.raises(FileNotFoundError, match="ingest first"):
        build_dataset("CISO", settings)


def test_build_dataset_is_idempotent(settings, frame):
    path = build_dataset("CISO", settings)
    report = path.with_name("carbon-quality-report.json")
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (path, report)]
    build_dataset("CISO", settings)
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in (path, report)]


def test_changed_factors_refresh_output_and_provenance(settings, frame, tmp_path):
    factors = tmp_path / "factors.yaml"
    factors.write_text("source: test\nfactors: {col: 100, sun: 100}\nexcluded: [bat]\n")
    path = build_dataset("CISO", settings, factors)
    report = path.with_name("carbon-quality-report.json")
    previous = json.loads(report.read_text())["factors_sha256"]
    factors.write_text("source: revised\nfactors: {col: 200, sun: 200}\nexcluded: [bat]\n")
    build_dataset("CISO", settings, factors)
    assert pd.read_parquet(path).carbon_intensity_g_per_kwh.iloc[0] == REVISED_FACTOR
    assert json.loads(report.read_text())["factors_sha256"] != previous


def test_build_dataset_relative_factors_path_is_independent_of_cwd(settings, frame, monkeypatch):
    monkeypatch.chdir(settings.data_dir)
    assert build_dataset("CISO", settings, Path("config/emission_factors.yaml")).exists()


def test_build_dataset_cli_without_key(settings, frame, monkeypatch):
    monkeypatch.setenv("CARBON_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("EIA_API_KEY", "")
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(app, ["build-dataset", "--region", "CISO"])
        assert result.exit_code == 0, result.output
        assert "hourly.parquet" in result.output
    finally:
        get_settings.cache_clear()


def test_build_dataset_cli_reports_missing_data(settings, monkeypatch):
    monkeypatch.setenv("CARBON_DATA_DIR", str(settings.data_dir))
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(app, ["build-dataset"])
        assert result.exit_code == 1
        assert "ingest first" in result.output
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "columns",
    [
        {"gen_col_mwh": [np.nan], "gen_sun_mwh": [np.nan]},
        {"gen_bat_mwh": [5.0]},
        {"demand_mwh": [5.0]},
    ],
)
def test_no_observed_covered_mix_is_nan_with_valid_json(settings, columns):
    index = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC", name="period").astype(
        "datetime64[ns, UTC]"
    )
    write_hourly(pd.DataFrame(columns, index=index), "CISO", "interim", settings.data_dir)
    path = build_dataset("CISO", settings)
    output = pd.read_parquet(path)
    assert output.carbon_intensity_g_per_kwh.isna().all()
    assert output.carbon_observed_coverage_fraction.isna().all()
    report = json.loads(path.with_name("carbon-quality-report.json").read_text())
    assert report["quality"]["missing_intensity_hours"] == 1


def test_unknown_fuel_does_not_replace_existing_output(settings, frame):
    path = build_dataset("CISO", settings)
    report = path.with_name("carbon-quality-report.json")
    before = [p.read_bytes() for p in (path, report)]
    frame["gen_newfuel_mwh"] = 1.0
    write_hourly(frame, "CISO", "interim", settings.data_dir)
    with pytest.raises(ValueError, match="newfuel"):
        build_dataset("CISO", settings)
    assert before == [p.read_bytes() for p in (path, report)]
