"""The /metrics endpoint exposes Prometheus text-format request metrics."""

# ruff: noqa: PLR2004

from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.config import Settings


class _HealthyService(ForecastService):
    def __init__(self) -> None:
        self.region = "CISO"
        self.settings = Settings(_env_file=None, demo_mode=True)

    def is_healthy(self):
        return True, "ok"


def test_metrics_endpoint_reports_request_counts():
    with TestClient(create_app(_HealthyService)) as client:
        client.get("/healthz")
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "carbon_api_requests_total" in response.text
        assert "carbon_api_request_duration_seconds" in response.text


def test_requests_carry_a_request_id_header():
    with TestClient(create_app(_HealthyService)) as client:
        response = client.get("/healthz")
        assert response.headers["X-Request-ID"]
        own_id = "caller-supplied-id"
        response = client.get("/healthz", headers={"X-Request-ID": own_id})
        assert response.headers["X-Request-ID"] == own_id
