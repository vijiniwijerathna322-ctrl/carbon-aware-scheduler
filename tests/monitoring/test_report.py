"""Replay respects both the fitted-model cutoff and observation boundaries."""

# ruff: noqa: PLR2004
import json
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from carbon_scheduler import cli
from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.config import Settings
from carbon_scheduler.monitoring import report as module
from carbon_scheduler.monitoring.report import _baseline_mae as actual_baseline


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    index = pd.date_range("2024-01-01", periods=220 * 24, freq="h", tz="UTC")
    # Exactly 80% coverage in a stationary deterministic residual pattern.
    series = pd.Series(100.0 + (np.arange(len(index)) % 5 == 0) * 2, index=index)
    fit_end = index[-22 * 24]
    calls = []

    class Model:
        def predict(self, history, issue):
            assert history.index.max() <= issue
            assert issue >= fit_end
            calls.append(issue)
            return pd.DataFrame(
                {
                    "target_time": pd.date_range(
                        issue + pd.Timedelta(hours=1), periods=48, freq="h"
                    ),
                    "horizon": np.arange(1, 49),
                    "lower": 99.0,
                    "median": 100.0,
                    "upper": 101.0,
                }
            )

    metadata = {
        "version": "synthetic-version",
        "fit_end": fit_end.isoformat(),
        "data_source": "raw",
        "alpha": 0.2,
        "exog_columns": [],
    }
    monkeypatch.setattr(module, "read_metadata", lambda *args, **kwargs: metadata)
    monkeypatch.setattr(module, "load_model", lambda *args, **kwargs: Model())
    monkeypatch.setattr(
        module, "load_backtest_series", lambda *args: (series.copy(), {"data_source": "raw"})
    )
    monkeypatch.setattr(module, "_baseline_mae", lambda *args: (0.4, 1000, "held-out synthetic"))
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        reports_dir=tmp_path / "reports",
    )
    return settings, series, metadata, calls


def test_replay_past_only_and_json_html(scenario):
    settings, series, _, calls = scenario
    result = module.build_monitor_report("CISO", settings, series.index[-1].to_pydatetime())
    assert result.status == "ok"
    assert calls
    assert result.coverage["demand_mwh"].n == 336
    decoded = json.loads(module.to_json(result))
    assert decoded["generated_at"].endswith("Z")
    assert decoded["model_version"]["demand_mwh"] == "synthetic-version"
    assert "ok" in module.to_html(result)
    result.reasons.append("<script>alert(1)</script>")
    assert "<script>" not in module.to_html(result)


def test_recent_fit_cannot_score_training_history(scenario):
    settings, series, metadata, _ = scenario
    metadata["fit_end"] = series.index[-1].isoformat()
    result = module.build_monitor_report("CISO", settings, series.index[-1].to_pydatetime())
    assert result.status == "insufficient_data"
    assert result.coverage["demand_mwh"].n == 0
    assert result.coverage["demand_mwh"].coverage is None
    assert "fit" in " ".join(result.reasons)


def test_shift_triggers_coverage_alert_within_seven_days(scenario):
    settings, series, _, _ = scenario
    series.iloc[-7 * 24 :] *= 1.3
    result = module.build_monitor_report("CISO", settings, series.index[-1].to_pydatetime())
    assert result.coverage["carbon_intensity_g_per_kwh"].status == "alert"
    assert result.status == "alert"
    assert any("coverage" in reason for reason in result.reasons)


def test_missing_current_data_is_counted(scenario):
    settings, series, _, _ = scenario
    series.iloc[-14 * 24 :] = np.nan
    result = module.build_monitor_report("CISO", settings, series.index[-1].to_pydatetime())
    assert result.status == "insufficient_data"
    assert result.replay["demand_mwh"]["excluded_nonfinite"] == 336
    assert result.feature_drift["demand_mwh/target"]["excluded_current"] == 336


def test_naive_now_rejected(scenario):
    with pytest.raises(ValueError, match="timezone"):
        module.build_monitor_report("CISO", scenario[0], datetime(2024, 1, 1))


def test_no_heldout_baseline_cannot_report_ok(scenario, monkeypatch):
    settings, series, _, _ = scenario
    monkeypatch.setattr(
        module, "_baseline_mae", lambda *args: (None, 0, "Calibration is not held-out")
    )
    report = module.build_monitor_report("CISO", settings, series.index[-1].to_pydatetime())
    assert report.coverage["demand_mwh"].status == "ok"
    assert report.status == "insufficient_data"
    assert report.mae_ratio["demand_mwh"] is None


def test_weather_monitoring_requires_vintage_logs(scenario):
    settings, series, _, _ = scenario
    directory = settings.models_dir / "CISO" / "demand_mwh"
    directory.mkdir(parents=True)
    (directory / "weather.json").write_text('{"approved":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="vintage"):
        module.build_monitor_report("CISO", settings, series.index[-1].to_pydatetime())


def test_baseline_excludes_recent_window_and_checks_configuration(tmp_path):
    settings = Settings(_env_file=None, reports_dir=tmp_path)
    start = pd.Timestamp("2024-02-01T00:00Z")
    index = pd.date_range(start - pd.Timedelta(hours=200), periods=201, freq="h")
    frame = pd.DataFrame(
        {"target_time": index, "issue_time": index - pd.Timedelta(hours=1), "y": 1.0, "median": 0.0}
    )
    frame.loc[200, "y"] = 100000
    path = tmp_path / "backtest_CISO_demand_mwh_cqr.parquet"
    frame.to_parquet(path, index=False)
    metadata = {
        "lgbm_parameters": {"n_estimators": 20},
        "seed": 42,
        "issue_step_h": 3,
        "tz": "UTC",
        "calibration_days": 90,
    }
    info = {
        "data_source": "raw",
        "timezone": "UTC",
        "calibration_days": 90,
        "model_parameters": json.dumps(
            {"n_estimators": 20, "seed": 42, "issue_step_h": 3, "n_jobs": 1}
        ),
    }
    path.with_suffix(".json").write_text(json.dumps(info), encoding="utf-8")
    value, n, _ = actual_baseline("demand_mwh", "CISO", settings, start, metadata, {})
    assert value == 1 and n == 200
    info["data_source"] = "processed"
    path.with_suffix(".json").write_text(json.dumps(info), encoding="utf-8")
    assert actual_baseline("demand_mwh", "CISO", settings, start, metadata, {})[0] is None


def test_cli_writes_reports_and_alert_exit_code(scenario, monkeypatch):
    settings, series, _, _ = scenario
    original = module.build_monitor_report
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        cli,
        "build_monitor_report",
        lambda region, config: original(region, config, series.index[-1].to_pydatetime()),
    )
    runner = CliRunner()
    result = runner.invoke(cli.app, ["monitor", "--region", "CISO"])
    assert result.exit_code == 0, result.output
    assert (settings.reports_dir / "monitor_CISO.json").is_file()
    assert (settings.reports_dir / "monitor_CISO.html").is_file()
    series.iloc[-7 * 24 :] *= 1.3
    assert runner.invoke(cli.app, ["monitor", "--region", "CISO"]).exit_code == 2


def test_status_endpoint_missing_valid_and_corrupt(scenario):
    settings, series, _, _ = scenario

    class Service(ForecastService):
        def __init__(self):
            self.region, self.settings = "CISO", settings

    with TestClient(create_app(Service)) as client:
        response = client.get("/v1/monitoring/status")
        assert response.status_code == 404
        assert response.json() == {"error": "no_report"}
        report = module.build_monitor_report("CISO", settings, series.index[-1].to_pydatetime())
        path = module.write_monitor_report(report, settings.reports_dir)
        assert client.get("/v1/monitoring/status").json()["status"] == "ok"
        assert client.get("/v1/monitoring/status?region=ERCO").status_code == 404
        path.write_text('{"status":"ok"}', encoding="utf-8")
        assert client.get("/v1/monitoring/status").status_code == 503
