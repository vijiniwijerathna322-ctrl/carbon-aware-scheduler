"""Approved synthetic variants use issue-time weather, otherwise preserve baseline."""

import json
import shutil

import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.demo import make_demo_assets
from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.registry import save_model
from carbon_scheduler.models.reporting import load_backtest_series
from carbon_scheduler.weather.client import WeatherClient, WeatherUnavailable


@pytest.fixture
def weather_settings(trained_settings, tmp_path):
    settings = trained_settings.model_copy(
        update={"data_dir": tmp_path / "data", "models_dir": tmp_path / "models"}
    )
    shutil.copytree(trained_settings.data_dir, settings.data_dir)
    shutil.copytree(trained_settings.models_dir, settings.models_dir)
    series, provenance = load_backtest_series("CISO", "demand_mwh", settings)
    issue = series.dropna().index[-1]
    exog = pd.DataFrame({"temperature_2m": 15.0}, index=series.index)
    model = ForecastModel(
        "demand_mwh",
        "America/Los_Angeles",
        exog=exog,
        exog_source="issue_vintage_forecast",
        lgbm_params={"n_estimators": 5},
    )
    model.fit(series, issue)
    model.metadata_.update(provenance)
    base = settings.models_dir / "CISO" / "demand_mwh"
    original = (base / "current.json").read_bytes()
    artifact = save_model(model, "CISO", settings.models_dir)
    (base / "current.json").write_bytes(original)
    (base / "weather.json").write_text(
        json.dumps({"version": artifact.name, "approved": True}), encoding="utf-8"
    )
    weather = pd.DataFrame(
        {"temperature_2m": 15.0},
        index=pd.date_range(issue + pd.Timedelta(hours=1), periods=48, freq="h"),
    )
    weather.attrs["received_at"] = (issue - pd.Timedelta(minutes=1)).isoformat()
    directory = settings.data_dir / "weather"
    directory.mkdir()
    weather.to_parquet(directory / "CISO_forecast.parquet")
    return settings, artifact.name, weather


def test_demo_mode_uses_baked_weather_snapshot(weather_settings, monkeypatch):
    settings, version, _ = weather_settings

    def no_network(*args, **kwargs):
        raise AssertionError("Demo must not request live weather")

    monkeypatch.setattr(WeatherClient, "fetch_forecast", no_network)
    service = ForecastService(settings)
    frame, meta = service.forecast("demand_mwh")
    assert meta.model_version == version
    assert not meta.notes
    assert np.isfinite(frame[["lower", "median", "upper"]]).all().all()
    assert service.current_models()["demand_mwh"]["version"] == version


def test_forecast_uses_weather_when_model_requires_it(weather_settings, monkeypatch):
    settings, version, weather = weather_settings
    settings = settings.model_copy(update={"demo_mode": False, "max_data_age_hours": 999999})
    monkeypatch.setattr(WeatherClient, "fetch_forecast", lambda *args, **kwargs: weather)
    _, meta = ForecastService(settings).forecast("demand_mwh")
    assert meta.model_version == version


def test_demo_export_keeps_weather_variant_and_snapshot(weather_settings, tmp_path):
    settings, version, _ = weather_settings
    output = tmp_path / "exported"
    make_demo_assets("CISO", settings, output)
    exported = settings.model_copy(
        update={"data_dir": output / "data", "models_dir": output / "models"}
    )
    _, meta = ForecastService(exported).forecast("demand_mwh")
    assert meta.model_version == version
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["weather_models"]["demand_mwh"] == version
    assert "data/weather/CISO_forecast.parquet" in manifest["sha256"]


@pytest.mark.parametrize("failure", ["network", "future", "missing", "unapproved"])
def test_weather_unavailable_falls_back_and_adds_note(weather_settings, monkeypatch, failure):
    settings, version, weather = weather_settings
    settings = settings.model_copy(update={"demo_mode": False, "max_data_age_hours": 999999})

    def fetch(*args, **kwargs):
        if failure == "network":
            raise WeatherUnavailable("Synthetic provider failure")
        if failure == "future":
            weather.attrs["received_at"] = weather.index[-1].isoformat()
        if failure == "missing":
            weather.iloc[0, 0] = np.nan
        return weather

    monkeypatch.setattr(WeatherClient, "fetch_forecast", fetch)
    pointer = settings.models_dir / "CISO" / "demand_mwh" / "weather.json"
    if failure == "unapproved":
        pointer.write_text(json.dumps({"version": version, "approved": False}), encoding="utf-8")
    service = ForecastService(settings)
    frame, meta = service.forecast("demand_mwh")
    assert meta.model_version != version
    assert "weather-free" in meta.notes[0]
    pointer.unlink()
    baseline, _ = ForecastService(settings).forecast("demand_mwh")
    pd.testing.assert_frame_equal(frame, baseline)
