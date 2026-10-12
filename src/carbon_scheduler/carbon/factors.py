"""Load lifecycle emission factors in grams CO2-equivalent per kWh."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from carbon_scheduler.config import PROJECT_ROOT

FuelCode = Annotated[str, Field(strict=True, pattern=r"^[a-z]+$")]
PositiveFactor = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]


class UnknownFuelError(ValueError):
    """Fuel codes have neither a configured factor nor an explicit exclusion."""


@dataclass(frozen=True)
class EmissionFactors:
    factors: Mapping[str, float]
    excluded: frozenset[str]
    source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "factors", MappingProxyType(dict(self.factors)))
        object.__setattr__(self, "excluded", frozenset(self.excluded))


class _FactorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factors: Annotated[dict[FuelCode, PositiveFactor], Field(min_length=1)]
    excluded: list[FuelCode]
    source: Annotated[str, Field(strict=True, min_length=1)]

    @model_validator(mode="after")
    def validate_metadata(self) -> "_FactorConfig":
        if not self.source.strip():
            raise ValueError("source must contain a nonempty citation")
        overlap = self.factors.keys() & set(self.excluded)
        if overlap:
            raise ValueError(f"factor and excluded codes overlap: {', '.join(sorted(overlap))}")
        return self


def load_emission_factors(path: Path) -> EmissionFactors:
    """Read safe YAML; resolve relative paths against the project root."""
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    try:
        with resolved.open(encoding="utf-8") as stream:
            values = yaml.safe_load(stream)
        config = _FactorConfig.model_validate(values)
    except (yaml.YAMLError, ValidationError) as exc:
        raise ValueError(f"Invalid emission factors configuration at {resolved}: {exc}") from exc
    return EmissionFactors(config.factors, frozenset(config.excluded), config.source)


def check_coverage(factors: EmissionFactors, fuel_codes: Iterable[str]) -> None:
    """Reject every code lacking either a factor or an explicit exclusion."""
    unknown = set(fuel_codes) - factors.factors.keys() - factors.excluded
    if unknown:
        raise UnknownFuelError(f"Unknown fuel codes: {', '.join(sorted(unknown))}")
