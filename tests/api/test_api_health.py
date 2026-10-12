"""Startup failures remain observable without exposing artifact paths."""

# ruff: noqa: PLR2004

from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.config import Settings


def test_missing_models_health_is_safe(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "private-data",
        models_dir=tmp_path / "private-models",
        demo_mode=True,
    )
    with TestClient(create_app(lambda: ForecastService(settings))) as client:
        response = client.get("/healthz")
        assert response.status_code == 503
        assert response.json()["reason"] == "models_unavailable"
        assert str(tmp_path) not in response.text


def test_openapi_has_endpoints_and_examples():
    schema = create_app().openapi()
    assert {"/healthz", "/v1/forecast", "/v1/schedule", "/v1/models/current"} <= set(
        schema["paths"]
    )
    assert schema["components"]["schemas"]["ScheduleRequest"]["examples"]
