"""Exceeding the configured per-minute request budget returns 429."""

# ruff: noqa: PLR2004

from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.rate_limit import FixedWindowRateLimiter
from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.config import Settings


def test_fixed_window_limiter_resets_after_the_window():
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.hit("a", now=0.0) is True
    assert limiter.hit("a", now=1.0) is True
    assert limiter.hit("a", now=2.0) is False
    assert limiter.hit("a", now=61.0) is True
    assert limiter.hit("b", now=2.0) is True


class _HealthyService(ForecastService):
    def __init__(self) -> None:
        self.region = "CISO"
        self.settings = Settings(_env_file=None, demo_mode=True)

    def is_healthy(self):
        return True, "ok"


def test_rate_limit_returns_429_once_exceeded():
    settings = Settings(_env_file=None, rate_limit_per_minute=2)
    with TestClient(create_app(_HealthyService, settings=settings)) as client:
        statuses = [client.get("/healthz").status_code for _ in range(4)]
        assert statuses[:2] == [200, 200]
        assert 429 in statuses[2:]


def test_rate_limit_response_shape():
    settings = Settings(_env_file=None, rate_limit_per_minute=1)
    with TestClient(create_app(_HealthyService, settings=settings)) as client:
        client.get("/healthz")
        response = client.get("/healthz")
        assert response.status_code == 429
        assert response.json()["error"] == "rate_limited"
