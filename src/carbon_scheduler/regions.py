"""Validated region metadata, resolved independently of the working directory."""

import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from carbon_scheduler.config import PROJECT_ROOT


class UnknownRegionError(ValueError):
    """The requested region is not configured."""


@dataclass(frozen=True)
class Region:
    code: str
    timezone: str
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Z][A-Z0-9_-]*", self.code) is None:
            raise ValueError("Region code must be a safe uppercase identifier")
        ZoneInfo(self.timezone)
        if not -90 <= self.lat <= 90 or not -180 <= self.lon <= 180:  # noqa: PLR2004
            raise ValueError("Region coordinates are out of range")


class Regions(dict[str, Region]):
    def __missing__(self, key: str) -> Region:
        raise UnknownRegionError(f"Unknown region {key!r}; choose from {', '.join(sorted(self))}")


def load_regions(path: Path = Path("config/regions.yaml")) -> dict[str, Region]:
    """Read configured regions and validate IANA timezones and coordinates."""
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    with resolved.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict) or not values:
        raise ValueError("Region configuration must be a nonempty mapping")
    return Regions({code: Region(code=code, **metadata) for code, metadata in values.items()})
