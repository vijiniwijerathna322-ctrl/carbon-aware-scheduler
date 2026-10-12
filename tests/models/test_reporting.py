# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from carbon_scheduler.cli import app
from carbon_scheduler.config import Settings, get_settings
from carbon_scheduler.ingest.store import write_hourly
from carbon_scheduler.models.evaluate import summarize
from carbon_scheduler.models.reporting import load_backtest_series, render_backtest_report


def test_report_contains_buckets_models_and_range():
    frame = pd.DataFrame(
        {
            "horizon": [1, 7, 25],
            "y": [1, 2, 3],
            "median": [1, 2, 3],
            "lower": [0, 1, 2],
            "upper": [2, 3, 4],
        }
    )
    summary = summarize(frame)
    summary.attrs.update(test_start="2024-01-01", test_end="2024-02-01")
    report = render_backtest_report({"naive": summary, "lgbm": summary}, "CISO", "demand_mwh")
    for text in ("1-6", "7-24", "25-48", "all", "naive", "lgbm", "2024-01-01", "2024-02-01"):
        assert text in report


def fixture_frame():
    hours = np.arange(40 * 24)
    return pd.DataFrame(
        {
            "demand_mwh": 100.0 + hours % 168,
            "carbon_intensity_g_per_kwh": 100.0 + hours % 168,
            "gen_ng_mwh": np.ones(len(hours)),
            "gen_sun_mwh": np.zeros(len(hours)),
        },
        index=pd.date_range(
            "2024-01-01", periods=len(hours), freq="h", tz="UTC", name="period"
        ).astype("datetime64[ns, UTC]"),
    )


def test_cli_naive_writes_fixture_report_without_key(tmp_path, monkeypatch):
    write_hourly(fixture_frame(), "CISO", "processed", tmp_path)
    monkeypatch.setenv("CARBON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EIA_API_KEY", "")
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(
            app,
            [
                "backtest",
                "--target",
                "demand_mwh",
                "--model",
                "naive",
                "--data-source",
                "processed",
                "--reports-dir",
                str(tmp_path / "reports"),
            ],
        )
        assert result.exit_code == 0, result.output
        stem = tmp_path / "reports/backtest_CISO_demand_mwh_naive"
        report = stem.with_suffix(".md").read_text()
        assert "retrospective" in report
        predictions = pd.read_parquet(stem.with_suffix(".parquet"))
        assert summarize(predictions).loc["all", "mae"] == 0
    finally:
        get_settings.cache_clear()


def test_raw_series_is_pointwise_and_does_not_use_retrospective_cleaned_values(tmp_path):
    raw = fixture_frame()
    raw.iloc[10, raw.columns.get_loc("demand_mwh")] = -1
    raw.iloc[11, raw.columns.get_loc("demand_mwh")] = np.nan
    write_hourly(raw, "CISO", "raw", tmp_path)
    cleaned = raw.copy()
    cleaned["demand_mwh"] = 9999.0
    write_hourly(cleaned, "CISO", "processed", tmp_path)
    settings = Settings(_env_file=None, data_dir=tmp_path)
    series, metadata = load_backtest_series("CISO", "demand_mwh", settings)
    assert series.iloc[10:12].isna().all()
    assert series.iloc[0] == 100
    assert metadata["data_source"] == "raw"
    carbon, carbon_metadata = load_backtest_series("CISO", "carbon_intensity_g_per_kwh", settings)
    assert carbon.eq(490).all()
    assert carbon_metadata["factors_sha256"]


def test_raw_future_perturbation_cannot_change_past_targets(tmp_path):
    raw = fixture_frame()
    settings = Settings(_env_file=None, data_dir=tmp_path)
    write_hourly(raw, "CISO", "raw", tmp_path)
    before, _ = load_backtest_series("CISO", "carbon_intensity_g_per_kwh", settings)
    raw.loc[raw.index > raw.index[300], "gen_sun_mwh"] = 1e6
    write_hourly(raw, "CISO", "raw", tmp_path)
    after, _ = load_backtest_series("CISO", "carbon_intensity_g_per_kwh", settings)
    pd.testing.assert_series_equal(before.iloc[:301], after.iloc[:301])


def test_invalid_target_and_missing_raw_have_clear_errors(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    with pytest.raises(ValueError, match="target"):
        load_backtest_series("CISO", "invalid", settings)
    with pytest.raises(FileNotFoundError, match="ingest"):
        load_backtest_series("CISO", "demand_mwh", settings)


def test_cli_invalid_model_fails_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("CARBON_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(
            app, ["backtest", "--model", "invalid", "--reports-dir", str(tmp_path / "reports")]
        )
        assert result.exit_code == 1
        assert "model" in result.output
        assert not (tmp_path / "reports").exists()
    finally:
        get_settings.cache_clear()
