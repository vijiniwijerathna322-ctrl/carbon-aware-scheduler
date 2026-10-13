"""Validated region metadata, resolved independently of the working directory."""

import math
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from carbon_scheduler.config import PROJECT_ROOT, get_settings


class UnknownRegionError(ValueError):
    """The requested region is not configured."""


@dataclass(frozen=True)
class WeatherPoint:
    lat: float
    lon: float
    weight: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.lat, self.lon, self.weight)):
            raise ValueError("Weather coordinates and weights must be finite")
        if not -90 <= self.lat <= 90 or not -180 <= self.lon <= 180:  # noqa: PLR2004
            raise ValueError("Weather coordinates are out of range")
        if self.weight <= 0:
            raise ValueError("Weather weights must be positive")


@dataclass(frozen=True)
class Region:
    code: str
    timezone: str
    lat: float
    lon: float
    weather_points: tuple[WeatherPoint, ...] = ()

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Z][A-Z0-9_-]*", self.code) is None:
            raise ValueError("Region code must be a safe uppercase identifier")
        ZoneInfo(self.timezone)
        if not -90 <= self.lat <= 90 or not -180 <= self.lon <= 180:  # noqa: PLR2004
            raise ValueError("Region coordinates are out of range")


class Regions(dict[str, Region]):
    def __missing__(self, key: str) -> Region:
        raise UnknownRegionError(f"Unknown region {key!r}; choose from {', '.join(sorted(self))}")


def load_regions(path: Path | None = None) -> dict[str, Region]:
    """Read configured regions and validate IANA timezones and coordinates."""
    path = get_settings().regions_path if path is None else path
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    with resolved.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict) or not values:
        raise ValueError("Region configuration must be a nonempty mapping")
    regions = Regions()
    for code, raw_metadata in values.items():
        metadata = dict(raw_metadata)
        points = metadata.pop("weather_points", [])
        regions[code] = Region(
            code=code, weather_points=tuple(WeatherPoint(**p) for p in points), **metadata
        )
    return regions
