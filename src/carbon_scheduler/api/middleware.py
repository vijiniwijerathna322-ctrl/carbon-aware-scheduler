"""Request correlation id, structured access logging and metrics recording."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from carbon_scheduler.api.metrics import REQUEST_COUNT, REQUEST_LATENCY
from carbon_scheduler.logging import request_id_var

access_logger = logging.getLogger("carbon_scheduler.access")

Handler = Callable[[Request], Awaitable[Response]]


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, records one access-log line, and updates metrics."""

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration = time.monotonic() - start
            route = request.scope.get("route")
            route_path = route.path if route is not None else request.url.path
            REQUEST_COUNT.labels(request.method, route_path, str(status_code)).inc()
            REQUEST_LATENCY.labels(request.method, route_path).observe(duration)
            access_logger.info(
                "%s %s %s %.1fms", request.method, route_path, status_code, duration * 1000
            )
            request_id_var.reset(token)
