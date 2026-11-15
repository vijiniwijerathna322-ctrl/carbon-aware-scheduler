"""Minimal in-memory fixed-window rate limiting.

`slowapi`'s automatic route-discovery (`SlowAPIMiddleware`) does not find
routes mounted through `APIRouter.include_router` on this FastAPI version:
`app.routes` holds opaque `_IncludedRouter` entries rather than flat routes,
so its matching loop never finds a handler and the limit never fires
(confirmed by direct testing, not by reading a changelog). Per-route
`@limiter.limit(...)` decorators work around that, but a hand-rolled
fixed-window counter is simpler to reason about, test deterministically,
and depend on for a single global limit.
"""

import time
from collections.abc import Awaitable, Callable
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

Handler = Callable[[Request], Awaitable[Response]]


class FixedWindowRateLimiter:
    """Thread-safe fixed-window counter keyed by an arbitrary string."""

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._counts: dict[str, tuple[int, float]] = {}

    def hit(self, key: str, *, now: float | None = None) -> bool:
        """Record one request for `key`; return whether it is within the limit."""
        current = time.monotonic() if now is None else now
        with self._lock:
            count, window_start = self._counts.get(key, (0, current))
            if current - window_start >= self.window_seconds:
                count, window_start = 0, current
            count += 1
            self._counts[key] = (count, window_start)
            return count <= self.limit


def rate_limit_key(request: Request) -> str:
    """Limit by API key when one is presented, else by client address."""
    key = request.headers.get("X-API-Key")
    if key:
        return key
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Returns 429 once `limiter`'s per-key budget is exceeded."""

    def __init__(self, app: ASGIApp, limiter: FixedWindowRateLimiter) -> None:
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        if not self.limiter.hit(rate_limit_key(request)):
            return JSONResponse(status_code=429, content={"error": "rate_limited"})
        return await call_next(request)
