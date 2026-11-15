"""FastAPI app factory, lifespan initialization and safe failure responses."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from carbon_scheduler import __version__
from carbon_scheduler.api.metrics import render_latest
from carbon_scheduler.api.middleware import ObservabilityMiddleware
from carbon_scheduler.api.rate_limit import FixedWindowRateLimiter, RateLimitMiddleware
from carbon_scheduler.api.routes import router, v1_router
from carbon_scheduler.api.service import ForecastService, ServiceUnavailableError
from carbon_scheduler.config import Settings, get_settings
from carbon_scheduler.logging import configure_logging


def create_app(
    service_factory: Callable[[], ForecastService] | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            app.state.service = (service_factory or (lambda: ForecastService(resolved_settings)))()
        except Exception:
            app.state.service = None
        yield

    app = FastAPI(
        title="Carbon-aware scheduler",
        version=__version__,
        lifespan=lifespan,
        description=(
            "Optional weather data: [Open-Meteo](https://open-meteo.com/), CC BY 4.0. "
            "The public weather API is for non-commercial use. Current production "
            "models remain weather-free; archive-weather ablation is exploratory."
        ),
    )
    app.state.settings = resolved_settings

    limiter = FixedWindowRateLimiter(resolved_settings.rate_limit_per_minute)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.add_middleware(ObservabilityMiddleware)

    origins = resolved_settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "Content-Type"],
        )

    @app.exception_handler(ServiceUnavailableError)
    async def unavailable(request: Request, error: ServiceUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": str(error)})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        body, content_type = render_latest()
        return Response(content=body, media_type=content_type)

    app.include_router(router)
    app.include_router(v1_router)
    return app


app = create_app()
