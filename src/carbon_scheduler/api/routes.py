"""Thin HTTP adapters for forecast and scheduling contracts."""

from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from carbon_scheduler.api.deps import get_service
from carbon_scheduler.api.schemas import (
    ForecastPoint,
    ForecastResponse,
    ScheduleRequest,
    ScheduleResponse,
)
from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.scheduler.models import Job
from carbon_scheduler.scheduler.optimizer import recommend

router = APIRouter()
Service = Annotated[ForecastService, Depends(get_service)]


def check_region(region: str, service: ForecastService) -> None:
    if region != service.region:
        raise HTTPException(status_code=404, detail="Region is not served")


@router.get("/healthz")
def health(service: Service) -> JSONResponse:
    healthy, reason = service.is_healthy()
    return JSONResponse(
        {"status": "ok" if healthy else "unhealthy", "reason": reason},
        status_code=200 if healthy else 503,
    )


@router.get("/v1/forecast", response_model=ForecastResponse)
def forecast(
    service: Service,
    region: str = "CISO",
    target: str = "carbon_intensity_g_per_kwh",
    horizon: Annotated[int, Query(ge=1, le=48)] = 48,
) -> ForecastResponse:
    check_region(region, service)
    try:
        frame, meta = service.forecast(target, horizon)
    except ValueError:
        raise HTTPException(status_code=422, detail="Unknown forecast target") from None
    return ForecastResponse(
        region=region,
        target=target,
        issue_time=meta.issue_time.to_pydatetime(),
        data_as_of=meta.data_as_of.to_pydatetime(),
        model_version=meta.model_version,
        alpha=meta.alpha,
        notes=list(meta.notes),
        points=[ForecastPoint.model_validate(row) for row in frame.to_dict("records")],
    )


@router.post("/v1/schedule", response_model=ScheduleResponse)
def schedule(body: ScheduleRequest, service: Service) -> ScheduleResponse:
    check_region(body.region, service)
    frame, meta = service.forecast("carbon_intensity_g_per_kwh")
    first = pd.Timestamp(frame.target_time.iloc[0])
    last_end = pd.Timestamp(frame.target_time.iloc[-1]) + pd.Timedelta(hours=1)
    if pd.Timestamp(body.deadline) > last_end:
        raise HTTPException(
            status_code=422,
            detail=(
                "Deadline exceeds max forecast horizon (48 hours); "
                f"latest end {last_end.isoformat()}"
            ),
        )
    notes = [
        "Carbon G4 missed nominal coverage; summed endpoints are not job-level confidence bounds."
    ]
    notes.extend(meta.notes)
    earliest = first if body.earliest_start is None else pd.Timestamp(body.earliest_start)
    if earliest < first:
        earliest = first
        notes.append("earliest_start clamped to the first available forecast hour.")
    try:
        job = Job(
            duration_hours=body.duration_hours,
            power_kw=body.power_kw,
            earliest_start=earliest.to_pydatetime(),
            deadline=body.deadline,
            interruptible=body.interruptible,
        )
        result = recommend(job, frame, body.strategy)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="No valid whole-hour job fits within the 48-hour forecast and deadline",
        ) from None
    if service.settings.demo_mode:
        notes.append(
            "Demo uses a frozen historical snapshot; times are relative to its forecast issue."
        )
    return ScheduleResponse(
        recommendation=result,
        forecast_issue_time=meta.issue_time.to_pydatetime(),
        data_as_of=meta.data_as_of.to_pydatetime(),
        model_version=meta.model_version,
        notes=notes,
    )


@router.get("/v1/models/current")
def current_models(service: Service) -> dict[str, Any]:
    return {"region": service.region, "models": service.current_models()}
