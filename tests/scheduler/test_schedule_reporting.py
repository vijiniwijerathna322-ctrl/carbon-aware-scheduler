"""Report provenance and CLI failure checks with offline fixtures."""

import json

import pandas as pd
import pytest
from typer.testing import CliRunner

from carbon_scheduler.cli import app
from carbon_scheduler.config import Settings
from carbon_scheduler.scheduler.reporting import run_schedule_backtest


def inputs(monkeypatch, tmp_path):
    index = pd.date_range("2026-01-01", periods=49, freq="h", tz="UTC").as_unit("ns")
    actual = pd.Series([300.0] + [100.0] * 48, index=index)
    provenance = {"data_source": "raw", "input_sha256": "input", "factors_sha256": "factors"}
    monkeypatch.setattr(
        "carbon_scheduler.scheduler.reporting.load_backtest_series",
        lambda *args: (actual, provenance),
    )
    source = tmp_path / "backtest_CISO_carbon_intensity_g_per_kwh_cqr.parquet"
    pd.DataFrame(
        {
            "issue_time": index[0],
            "target_time": index[1:],
            "horizon": range(1, 49),
            "lower": 90.0,
            "median": 100.0,
            "upper": 110.0,
        }
    ).to_parquet(source)
    metadata = {**provenance, "test_start": index[0].isoformat(), "test_end": index[-1].isoformat()}
    source.with_suffix(".json").write_text(json.dumps(metadata))
    return source, metadata


def test_report_and_cli(monkeypatch, tmp_path):
    inputs(monkeypatch, tmp_path)
    result = CliRunner().invoke(app, ["schedule-backtest", "--reports-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    report = tmp_path / "schedule_backtest_CISO.md"
    text = report.read_text(encoding="utf-8")
    assert "G5: PASS" in text
    assert "## median" in text and "## upper" in text
    assert "forecast_sha256" in text
    results = pd.read_parquet(report.with_suffix(".parquet"))
    assert (results.status == "scored").all()


def test_provenance_mismatch_rejected(monkeypatch, tmp_path):
    source, metadata = inputs(monkeypatch, tmp_path)
    metadata["input_sha256"] = "changed"
    source.with_suffix(".json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="provenance disagree"):
        run_schedule_backtest("CISO", Settings(_env_file=None), tmp_path)


def test_missing_forecasts_cli_failure(monkeypatch, tmp_path):
    inputs(monkeypatch, tmp_path)
    result = CliRunner().invoke(
        app, ["schedule-backtest", "--reports-dir", str(tmp_path / "missing")]
    )
    assert result.exit_code == 1
    assert "Schedule backtest failed" in result.output
