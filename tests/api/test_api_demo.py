"""Copied demo snapshots load actual models without API keys."""

# ruff: noqa: PLR2004

import pytest

from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.config import Settings
from carbon_scheduler.demo import make_demo_assets
from carbon_scheduler.ingest.store import read_hourly


def test_demo_assets_load_and_truncate(trained_settings, tmp_path):
    output = tmp_path / "demo"
    make_demo_assets("CISO", trained_settings, output, history_days=30)
    settings = Settings(
        _env_file=None, data_dir=output / "data", models_dir=output / "models", demo_mode=True
    )
    frame = read_hourly("CISO", "raw", settings.data_dir)
    assert len(frame) == 30 * 24
    service = ForecastService(settings)
    assert service.is_healthy() == (True, "ok")
    assert len(service.forecast("demand_mwh")[0]) == 48
    assert (output / "manifest.json").is_file()
    with pytest.raises(FileExistsError):
        make_demo_assets("CISO", trained_settings, output)


def test_demo_rejects_insufficient_history(trained_settings, tmp_path):
    with pytest.raises(ValueError, match="history_days"):
        make_demo_assets("CISO", trained_settings, tmp_path / "demo", history_days=1)
