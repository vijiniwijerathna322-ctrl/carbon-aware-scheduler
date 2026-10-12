"""Public responses, validation, staleness and sanitized failures."""

# ruff: noqa: PLR2004

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastMeta, ForecastService, ServiceUnavailableError
from carbon_scheduler.config import Settings

ISSUE = pd.Timestamp("2026-10-11T06:00:00Z")


class StubService(ForecastService):
    def __init__(self, *, demo: bool = True):
        self.region = "CISO"
        self.settings = Settings(_env_file=None, demo_mode=demo)

    def is_healthy(self):
        return True, "ok"

    def forecast(self, target, horizon=48):
        if not self.settings.demo_mode:
            raise ServiceUnavailableError("data_stale")
        if target not in ("demand_mwh", "carbon_intensity_g_per_kwh"):
            raise ValueError("target")
        return pd.DataFrame(
            {
                "target_time": pd.date_range(
                    ISSUE + pd.Timedelta(hours=1), periods=horizon, freq="h"
                ),
                "horizon": range(1, horizon + 1),
                "lower": 90.0,
                "median": 100.0,
                "upper": 110.0,
            }
        ), ForecastMeta(ISSUE, ISSUE, "demo-version", 0.2)

    def current_models(self):
        return {"carbon_intensity_g_per_kwh": {"version": "demo-version"}}


@pytest.fixture
def client():
    with TestClient(create_app(StubService)) as client:
        yield client


def body(**updates):
    return {"duration_hours": 2, "power_kw": 7, "deadline": "2026-10-12T06:00:00Z", **updates}


def test_forecast_health_models(client):
    assert client.get("/healthz").status_code == 200
    response = client.get("/v1/forecast?horizon=6")
    assert response.status_code == 200
    result = response.json()
    assert len(result["points"]) == 6
    assert result["issue_time"].endswith("Z")
    assert result["data_as_of"].endswith("Z")
    assert result["points"][0]["target_time"].endswith("Z")
    assert result["model_version"] == "demo-version"
    assert client.get("/v1/models/current").json()["models"]


@pytest.mark.parametrize("query", ["horizon=0", "horizon=49", "target=unknown"])
def test_forecast_validation(client, query):
    assert client.get("/v1/forecast?" + query).status_code == 422


def test_unknown_region(client):
    assert client.get("/v1/forecast?region=unknown").status_code == 404
    assert client.post("/v1/schedule", json=body(region="ERCO")).status_code == 404


def test_schedule_and_clamp(client):
    response = client.post("/v1/schedule", json=body(earliest_start="2026-10-10T00:00:00Z"))
    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"]["start"] == "2026-10-11T07:00:00Z"
    assert any("clamped" in note for note in result["notes"])
    response = client.post("/v1/schedule", json=body(interruptible=True, strategy="upper"))
    assert len(response.json()["recommendation"]["hours"]) == 2


@pytest.mark.parametrize(
    "updates",
    [
        {"deadline": "2026-10-14T00:00:00Z"},
        {"deadline": "2026-10-11T06:00:00Z"},
        {"deadline": "2026-10-12T06:00:00"},
        {"earliest_start": "2026-10-11T07:00:00"},
        {"power_kw": 0},
        {"power_kw": True},
        {"duration_hours": True},
        {"strategy": "other"},
    ],
)
def test_schedule_validation(client, updates):
    response = client.post("/v1/schedule", json=body(**updates))
    assert response.status_code == 422
    if updates.get("deadline") == "2026-10-14T00:00:00Z":
        assert "48 hours" in response.text


def test_stale_response_and_startup_exception():
    with TestClient(create_app(lambda: StubService(demo=False))) as client:
        response = client.get("/v1/forecast")
        assert response.status_code == 503
        assert response.json() == {"error": "data_stale"}

    def broken():
        raise RuntimeError("C:/private/secret-model.joblib traceback")

    with TestClient(create_app(broken)) as client:
        response = client.get("/healthz")
        assert response.status_code == 503
        assert "private" not in response.text
        assert "traceback" not in response.text


def test_unexpected_error_is_sanitized():
    class BrokenService(StubService):
        def forecast(self, *args, **kwargs):
            raise RuntimeError("C:/private/model.joblib traceback")

    with TestClient(create_app(BrokenService), raise_server_exceptions=False) as client:
        response = client.get("/v1/forecast")
        assert response.status_code == 500
        assert response.json() == {"error": "internal_error"}
