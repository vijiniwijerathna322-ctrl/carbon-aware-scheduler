import logging
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from carbon_scheduler.config import MissingApiKeyError, Settings, get_settings
from carbon_scheduler.logging import configure_logging


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for name in ("EIA_API_KEY", "LOG_LEVEL", "CARBON_DATA_DIR", "CARBON_MODELS_DIR"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("CARBON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CARBON_MODELS_DIR", str(tmp_path / "artifacts"))
    settings = Settings(_env_file=None)
    assert settings.data_dir == tmp_path
    assert settings.models_dir == tmp_path / "artifacts"


def test_key_not_in_repr_or_logs(monkeypatch, caplog):
    monkeypatch.setenv("EIA_API_KEY", "SECRET123")
    settings = Settings(_env_file=None)
    assert "SECRET123" not in repr(settings)
    with caplog.at_level(logging.INFO):
        logging.getLogger("settings-test").info("Settings: %r", settings)
    assert "SECRET123" not in caplog.text
    assert settings.require_eia_key() == "SECRET123"


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_raises_clear_error(monkeypatch, key):
    if key is not None:
        monkeypatch.setenv("EIA_API_KEY", key)
    with pytest.raises(MissingApiKeyError, match="EIA_API_KEY"):
        Settings(_env_file=None).require_eia_key()


def test_bad_log_level_rejected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_defaults_and_relative_overrides_ignore_working_directory(monkeypatch, tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert settings.data_dir == project_root / "data"
    assert settings.models_dir == project_root / "models"
    monkeypatch.setenv("CARBON_DATA_DIR", "custom/data")
    assert Settings(_env_file=None).data_dir == project_root / "custom/data"


def test_dotenv_loading_and_environment_precedence(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("EIA_API_KEY=local-secret\nLOG_LEVEL=DEBUG\nUNKNOWN=value\n")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    settings = Settings(_env_file=dotenv)
    assert settings.log_level == "ERROR"
    assert settings.require_eia_key() == "local-secret"


def test_settings_are_cached(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    assert get_settings() is get_settings()
    assert get_settings().log_level == "WARNING"


def test_logging_uses_utc(monkeypatch):
    calls = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.update(kwargs))
    configure_logging("DEBUG")
    handler = calls["handlers"][0]
    assert handler.formatter.converter is time.gmtime
    assert calls["level"] == "DEBUG"
