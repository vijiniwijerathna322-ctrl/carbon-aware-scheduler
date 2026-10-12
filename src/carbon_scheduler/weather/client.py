"""Bounded Open-Meteo requests with point/range caching and missingness retention."""

import hashlib
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, cast

import httpx
import pandas as pd

from carbon_scheduler.models.base import validate_series
from carbon_scheduler.regions import WeatherPoint

VARIABLES = ("temperature_2m", "cloud_cover", "shortwave_radiation", "wind_speed_100m")
UNITS = dict(zip(VARIABLES, ("\u00b0C", "%", "W/m\u00b2", "km/h"), strict=True))
ENDPOINTS = {
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "historical_forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "forecast": "https://api.open-meteo.com/v1/forecast",
}


class WeatherUnavailable(RuntimeError):
    """No valid provider response is available; a baseline can still serve."""


class WeatherClient:
    def __init__(
        self,
        cache_dir: Path,
        http: httpx.Client | None = None,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.cache_dir = cache_dir
        self.http = http or httpx.Client(timeout=60)
        self._owns_http = http is None
        self.clock = clock

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def _point(self, point: WeatherPoint, source: str, extra: dict[str, str | int]) -> pd.DataFrame:
        params = {
            "latitude": point.lat,
            "longitude": point.lon,
            "hourly": ",".join(VARIABLES),
            "timezone": "UTC",
            "wind_speed_unit": "kmh",
            **extra,
        }
        identifier = hashlib.sha256(
            json.dumps({"source": source, "params": params}, sort_keys=True).encode()
        ).hexdigest()
        path = self.cache_dir / f"{identifier}.parquet"
        now = pd.Timestamp(self.clock()).tz_convert("UTC")
        if path.is_file():
            try:
                frame = pd.read_parquet(path)
                age = now - pd.Timestamp(frame.attrs["received_at"])
                if source != "forecast" or pd.Timedelta(0) <= age < pd.Timedelta(hours=1):
                    return frame
            except (OSError, ValueError, KeyError, TypeError):
                pass
        try:
            response = self.http.get(ENDPOINTS[source], params=params)
            response.raise_for_status()
            payload = response.json()
            if payload.get("utc_offset_seconds") != 0 or payload.get("error"):
                raise ValueError("Expected UTC hourly weather")
            hourly = payload["hourly"]
            index = pd.DatetimeIndex(pd.to_datetime(hourly["time"], utc=True)).as_unit("ns")
            if (
                not len(index)
                or not index.is_unique
                or not index.is_monotonic_increasing
                or not index.equals(index.floor("h"))
            ):
                raise ValueError("Invalid hourly weather timestamps")
            if any(payload["hourly_units"].get(column) != UNITS[column] for column in VARIABLES):
                raise ValueError("Weather units differ from the requested contract")
            frame = pd.DataFrame(
                {column: pd.to_numeric(hourly[column], errors="raise") for column in VARIABLES},
                index=index,
            ).astype(float)
            frame = frame.reindex(pd.date_range(index[0], index[-1], freq="h"))
            for column in frame:
                validate_series(frame[column])
            frame.attrs.update(
                source=source,
                units=UNITS,
                received_at=pd.Timestamp(self.clock()).tz_convert("UTC").isoformat(),
                url=ENDPOINTS[source],
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise WeatherUnavailable("Weather provider unavailable or response invalid") from error
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=self.cache_dir, suffix=".parquet", delete=False) as stream:
                temporary = Path(stream.name)
            try:
                frame.to_parquet(temporary)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError:
            # A read-only serving filesystem can still consume the fresh response.
            pass
        return frame

    def _weighted(
        self, points: Sequence[WeatherPoint], source: str, extra: dict[str, str | int]
    ) -> pd.DataFrame:
        if not points:
            raise ValueError("At least one weather point is required")
        frames = [self._point(point, source, extra) for point in points]
        index = frames[0].index
        for frame in frames[1:]:
            index = index.union(frame.index)
        total = sum(point.weight for point in points)
        # Any missing contributing point yields NaN; never renormalize over fewer points.
        values = frames[0].reindex(index) * points[0].weight
        for frame, point in zip(frames[1:], points[1:], strict=True):
            values = values + frame.reindex(index) * point.weight
        values = values / total
        result = pd.DataFrame(values, index=index)
        result.attrs.update(
            cast(dict[str, Any], frames[0].attrs),
            points=[asdict(point) for point in points],
            missing_cells=int(result.isna().sum().sum()),
        )
        result.attrs["received_at"] = max(
            pd.Timestamp(frame.attrs["received_at"]) for frame in frames
        ).isoformat()
        return result

    def fetch_history(
        self,
        points: Sequence[WeatherPoint],
        start: date,
        end: date,
        source: Literal["archive", "historical_forecast"] = "archive",
    ) -> pd.DataFrame:
        if source not in ("archive", "historical_forecast") or start > end:
            raise ValueError("Invalid history source or date interval")
        frame = self._weighted(
            points, source, {"start_date": start.isoformat(), "end_date": end.isoformat()}
        )
        index = pd.date_range(
            pd.Timestamp(start, tz="UTC"),
            pd.Timestamp(end + timedelta(days=1), tz="UTC"),
            freq="h",
            inclusive="left",
        ).as_unit("ns")
        result = frame.reindex(index)
        result.attrs.update(
            cast(dict[str, Any], frame.attrs), missing_cells=int(result.isna().sum().sum())
        )
        return result

    def fetch_forecast(self, points: Sequence[WeatherPoint], hours: int = 48) -> pd.DataFrame:
        if isinstance(hours, bool) or not 1 <= hours <= 72:  # noqa: PLR2004
            raise ValueError("Forecast hours must be in 1..72")
        return self._weighted(points, "forecast", {"forecast_hours": hours})
