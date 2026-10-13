"""FastAPI app factory, lifespan initialization and safe failure responses."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from carbon_scheduler import __version__
from carbon_scheduler.api.routes import router
from carbon_scheduler.api.service import ForecastService, ServiceUnavailableError
from carbon_scheduler.config import get_settings


def create_app(service_factory: Callable[[], ForecastService] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            app.state.service = (service_factory or (lambda: ForecastService(get_settings())))()
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

    @app.exception_handler(ServiceUnavailableError)
    async def unavailable(request: Request, error: ServiceUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": str(error)})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    app.include_router(router)
    return app


app = create_app()
