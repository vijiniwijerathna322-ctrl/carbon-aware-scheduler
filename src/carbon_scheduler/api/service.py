"""Immutable startup snapshots, model validation and target-specific freshness."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from carbon_scheduler.config import Settings
from carbon_scheduler.models.registry import (
    ModelIncompatibleError,
    ModelNotFoundError,
    load_model,
    read_metadata,
)
from carbon_scheduler.models.reporting import TARGETS, load_backtest_series
from carbon_scheduler.regions import load_regions
from carbon_scheduler.weather.client import WeatherClient, WeatherUnavailable


class ServiceUnavailableError(RuntimeError):
    """Sanitized failure suitable for an HTTP response."""


@dataclass(frozen=True)
class ForecastMeta:
    issue_time: pd.Timestamp
    data_as_of: pd.Timestamp
    model_version: str
    alpha: float
    notes: tuple[str, ...] = ()


class ForecastService:
    def __init__(self, settings: Settings, region: str | None = None) -> None:
        self.settings = settings
        region = region or next(iter(load_regions(settings.regions_path)))
        self.region = region
        self._reason = "ok"
        self._forecasts: dict[str, tuple[pd.DataFrame, ForecastMeta]] = {}
        self._models: dict[str, dict[str, Any]] = {}
        try:
            load_regions(settings.regions_path)[region]
            for target in TARGETS:
                metadata = read_metadata(
                    region, target, settings.models_dir, regions_path=settings.regions_path
                )
                model = load_model(
                    region,
                    target,
                    settings.models_dir,
                    metadata["version"],
                    regions_path=settings.regions_path,
                )
                if metadata.get("data_source") != "raw" or metadata.get("exog_columns"):
                    raise ModelIncompatibleError(
                        "Serving requires a raw-trained weather-free fallback"
                    )
                series, provenance = load_backtest_series(region, target, settings)
                if target == TARGETS[1] and metadata.get("factors_sha256") != provenance.get(
                    "factors_sha256"
                ):
                    raise ModelIncompatibleError("Carbon factor configuration differs")
                issue = pd.Timestamp(series.dropna().index[-1])
                if pd.Timestamp(metadata["fit_end"]) > issue:
                    raise ModelIncompatibleError("Model is newer than the finite snapshot")
                frame = model.predict(series, issue)
                if not np.isfinite(frame[["lower", "median", "upper"]].to_numpy()).all():
                    raise ModelIncompatibleError("Model returned nonfinite predictions")
                meta = ForecastMeta(issue, issue, metadata["version"], float(metadata["alpha"]))
                frame, meta = self._with_weather(target, series, frame, meta, provenance)
                metadata = read_metadata(
                    region,
                    target,
                    settings.models_dir,
                    meta.model_version,
                    regions_path=settings.regions_path,
                )
                self._forecasts[target] = (frame.copy(deep=True), meta)
                self._models[target] = {
                    key: metadata[key]
                    for key in ("version", "target", "alpha", "fit_end", "trained_at")
                }
                for field in ("fit_end", "trained_at"):
                    self._models[target][field] = (
                        pd.Timestamp(metadata[field])
                        .tz_convert("UTC")
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
        except ModelNotFoundError:
            self._reason = "models_unavailable"
        except ModelIncompatibleError:
            self._reason = "models_incompatible"
        except OSError:
            self._reason = "data_unavailable"
        except (ValueError, KeyError, IndexError, RuntimeError):
            self._reason = "snapshot_invalid"
        if self._reason != "ok":
            self._forecasts.clear()
            self._models.clear()

    def _with_weather(
        self,
        target: str,
        series: pd.Series,
        baseline: pd.DataFrame,
        meta: ForecastMeta,
        provenance: dict[str, Any],
    ) -> tuple[pd.DataFrame, ForecastMeta]:
        """Optional approved variant; any failure preserves the startup baseline."""
        pointer = self.settings.models_dir / self.region / target / "weather.json"
        if not pointer.is_file():
            return baseline, meta
        try:
            choice = json.loads(pointer.read_text(encoding="utf-8"))
            if not isinstance(choice, dict):
                raise WeatherUnavailable("Invalid weather variant pointer")
            metadata = read_metadata(
                self.region,
                target,
                self.settings.models_dir,
                choice["version"],
                regions_path=self.settings.regions_path,
            )
            if (
                choice.get("approved") is not True
                or metadata.get("exog_source") != "issue_vintage_forecast"
                or metadata.get("data_source") != "raw"
                or not metadata.get("exog_columns")
                or pd.Timestamp(metadata["fit_end"]) > meta.issue_time
            ):
                raise WeatherUnavailable("Weather variant is not approved for serving")
            if target == TARGETS[1] and metadata.get("factors_sha256") != provenance.get(
                "factors_sha256"
            ):
                raise WeatherUnavailable("Weather variant carbon factors differ")
            model = load_model(
                self.region,
                target,
                self.settings.models_dir,
                choice["version"],
                regions_path=self.settings.regions_path,
            )
            if self.settings.demo_mode:
                weather = pd.read_parquet(
                    self.settings.data_dir / "weather" / f"{self.region}_forecast.parquet"
                )
            else:
                client = WeatherClient(self.settings.data_dir / "weather" / "cache")
                try:
                    weather = client.fetch_forecast(
                        load_regions(self.settings.regions_path)[self.region].weather_points,
                        issue_time=meta.issue_time,
                    )
                finally:
                    client.close()
            available = pd.Timestamp(weather.attrs["received_at"])
            if available.tzinfo is None or available > meta.issue_time:
                raise WeatherUnavailable("Weather was unavailable at the reported issue time")
            index = pd.date_range(meta.issue_time + pd.Timedelta(hours=1), periods=48, freq="h")
            weather = weather.reindex(index)[metadata["exog_columns"]]
            if not np.isfinite(weather.to_numpy()).all():
                raise WeatherUnavailable("Weather forecast does not cover all target hours")
            frame = model.predict(series, meta.issue_time, exog=weather)
            if not np.isfinite(frame[["lower", "median", "upper"]].to_numpy()).all():
                raise WeatherUnavailable("Weather model returned invalid predictions")
            return frame, ForecastMeta(
                meta.issue_time, meta.data_as_of, metadata["version"], float(metadata["alpha"])
            )
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            return baseline, ForecastMeta(
                meta.issue_time,
                meta.data_as_of,
                meta.model_version,
                meta.alpha,
                ("Weather variant unavailable or unapproved; using the weather-free model.",),
            )

    def _fresh(self, meta: ForecastMeta) -> bool:
        return self.settings.demo_mode or (
            pd.Timestamp(datetime.now(UTC)) - meta.data_as_of
            <= pd.Timedelta(hours=self.settings.max_data_age_hours)
        )

    def is_healthy(self) -> tuple[bool, str]:
        if self._reason != "ok":
            return False, self._reason
        if not all(self._fresh(meta) for _, meta in self._forecasts.values()):
            return False, "data_stale"
        return True, "ok"

    def forecast(self, target: str, horizon: int = 48) -> tuple[pd.DataFrame, ForecastMeta]:
        if target not in TARGETS:
            raise ValueError("Unknown forecast target")
        if not 1 <= horizon <= 48:  # noqa: PLR2004
            raise ValueError("Horizon must be between 1 and 48 hours")
        if self._reason != "ok":
            raise ServiceUnavailableError(self._reason)
        frame, meta = self._forecasts[target]
        if not self._fresh(meta):
            raise ServiceUnavailableError("data_stale")
        return frame.iloc[:horizon].copy(deep=True), meta

    def current_models(self) -> dict[str, dict[str, Any]]:
        healthy, reason = self.is_healthy()
        if not healthy:
            raise ServiceUnavailableError(reason)
        return {target: dict(metadata) for target, metadata in self._models.items()}
