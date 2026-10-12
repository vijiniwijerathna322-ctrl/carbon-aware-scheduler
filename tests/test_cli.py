import pytest
from typer.testing import CliRunner

from carbon_scheduler import __version__
from carbon_scheduler.cli import app
from carbon_scheduler.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_version_command():
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_works_without_api_key():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout


def test_version_runs_from_another_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
