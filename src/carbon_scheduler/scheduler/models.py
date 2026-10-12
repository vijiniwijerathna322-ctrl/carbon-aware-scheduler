"""Validated scheduling inputs and emission estimates."""

from datetime import UTC, datetime, timedelta
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Strategy = Literal["median", "upper"]


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    duration_hours: int = Field(ge=1, le=168, strict=True)
    power_kw: float = Field(gt=0, allow_inf_nan=False)
    earliest_start: AwareDatetime
    deadline: AwareDatetime
    interruptible: bool = False

    @field_validator("earliest_start", "deadline")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.deadline - self.earliest_start < timedelta(hours=self.duration_hours):
            raise ValueError("Deadline must allow the full job duration")
        return self


class Recommendation(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    strategy: Strategy
    emissions_gco2_median: float
    emissions_gco2_lower: float
    emissions_gco2_upper: float
    baseline_start: AwareDatetime
    baseline_emissions_gco2_median: float
    expected_savings_pct: float
    delay_hours: int
    hours: list[datetime] | None = None
