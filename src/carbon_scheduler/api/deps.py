"""App-scoped dependency shared across read-only requests."""

from typing import cast

from fastapi import Request

from carbon_scheduler.api.service import ForecastService, ServiceUnavailableError


def get_service(request: Request) -> ForecastService:
    service = cast(ForecastService | None, request.app.state.service)
    if service is None:
        raise ServiceUnavailableError("startup_failed")
    return service
