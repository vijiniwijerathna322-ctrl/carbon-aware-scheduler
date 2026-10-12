"""Public API contracts with timezone-aware UTC responses."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from carbon_scheduler.scheduler.models import Recommendation, Strategy


class ForecastPoint(BaseModel):
    target_time: AwareDatetime
    horizon: int = Field(ge=1, le=48)
    lower: float = Field(allow_inf_nan=False)
    median: float = Field(allow_inf_nan=False)
    upper: float = Field(allow_inf_nan=False)


class ForecastResponse(BaseModel):
    region: str
    target: str
    issue_time: AwareDatetime
    data_as_of: AwareDatetime
    model_version: str
    alpha: float
    points: list[ForecastPoint]
    notes: list[str] = Field(default_factory=list)


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "region": "CISO",
                    "duration_hours": 2,
                    "power_kw": 7,
                    "earliest_start": None,
                    "deadline": "2026-10-12T06:00:00Z",
                    "strategy": "median",
                    "interruptible": False,
                }
            ]
        },
    )
    region: str = "CISO"
    duration_hours: int = Field(
        ge=1, le=168, strict=True, description="Required one-hour work slots."
    )
    power_kw: float = Field(
        gt=0, strict=True, allow_inf_nan=False, description="Constant power during execution."
    )
    earliest_start: AwareDatetime | None = Field(
        default=None, description="Defaults to first forecast hour; earlier arrivals are clamped."
    )
    deadline: AwareDatetime = Field(
        description="All selected whole hours must finish by this time."
    )
    strategy: Strategy = Field(
        default="median",
        description="Upper minimizes summed endpoints; it is not a calibrated job-level guarantee.",
    )
    interruptible: bool = False


class ScheduleResponse(BaseModel):
    recommendation: Recommendation
    forecast_issue_time: AwareDatetime
    data_as_of: AwareDatetime
    model_version: str
    notes: list[str]
