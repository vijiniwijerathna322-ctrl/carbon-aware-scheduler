"""API-key auth is disabled when unset and enforced when configured."""

# ruff: noqa: PLR2004

import pandas as pd
from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastMeta, ForecastService
from carbon_scheduler.config import Settings

ISSUE = pd.Timestamp("2026-10-11T06:00:00Z")


class _HealthyService(ForecastService):
    def __init__(self) -> None:
        self.region = "CISO"
        self.settings = Settings(_env_file=None, demo_mode=True)

    def is_healthy(self):
        return True, "ok"

    def forecast(self, target, horizon=48):
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


def test_auth_disabled_by_default():
    settings = Settings(_env_file=None, api_keys=None)
    with TestClient(create_app(_HealthyService, settings=settings)) as client:
        assert client.get("/v1/forecast").status_code == 200
        assert client.get("/healthz").status_code == 200


def test_auth_required_when_keys_configured():
    settings = Settings(_env_file=None, api_keys="secret-one, secret-two")
    with TestClient(create_app(_HealthyService, settings=settings)) as client:
        assert client.get("/v1/forecast").status_code == 401
        assert client.get("/v1/forecast", headers={"X-API-Key": "wrong"}).status_code == 401
        response = client.get("/v1/forecast", headers={"X-API-Key": "secret-two"})
        assert response.status_code == 200
        # Health and metrics stay open regardless of configured keys.
        assert client.get("/healthz").status_code == 200
        assert client.get("/metrics").status_code == 200
