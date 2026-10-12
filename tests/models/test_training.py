# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from carbon_scheduler.cli import app
from carbon_scheduler.config import Settings, get_settings
from carbon_scheduler.ingest.store import write_hourly
from carbon_scheduler.models.registry import load_model, read_metadata
from carbon_scheduler.models.training import train_region


def test_train_region_saves_both_targets_and_reload(tmp_path):
    hours = np.arange(150 * 24)
    frame = pd.DataFrame(
        {
            "demand_mwh": 100.0 + hours % 24,
            "gen_ng_mwh": 50.0 + hours % 24,
            "gen_sun_mwh": np.maximum(np.sin(hours / 24 * 2 * np.pi), 0) * 20,
        },
        index=pd.date_range(
            "2024-01-01", periods=len(hours), freq="h", tz="UTC", name="period"
        ).astype("datetime64[ns, UTC]"),
    )
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", models_dir=tmp_path / "models")
    write_hourly(frame, "CISO", "raw", settings.data_dir)
    artifacts = train_region("CISO", settings, lgbm_params={"n_estimators": 10})
    assert set(artifacts) == {"demand_mwh", "carbon_intensity_g_per_kwh"}
    for target in artifacts:
        model = load_model("CISO", target, settings.models_dir)
        metadata = read_metadata("CISO", target, settings.models_dir)
        assert metadata["metrics"]["scope"] == "reused calibration window; not held-out"
        assert metadata["data_source"] == "raw"
        assert model.metadata()["n_calibration"] > 0


def test_missing_history_has_ingest_hint(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="ingest"):
        train_region("CISO", settings)


def test_cli_train_fails_helpfully_without_history(tmp_path, monkeypatch):
    monkeypatch.setenv("CARBON_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(app, ["train", "--region", "CISO"])
        assert result.exit_code == 1
        assert "ingest" in result.output
    finally:
        get_settings.cache_clear()
