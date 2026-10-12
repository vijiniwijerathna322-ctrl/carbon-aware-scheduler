"""Immutable startup snapshots, model validation and target-specific freshness."""

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


class ServiceUnavailableError(RuntimeError):
    """Sanitized failure suitable for an HTTP response."""


@dataclass(frozen=True)
class ForecastMeta:
    issue_time: pd.Timestamp
    data_as_of: pd.Timestamp
    model_version: str
    alpha: float


class ForecastService:
    def __init__(self, settings: Settings, region: str = "CISO") -> None:
        self.settings = settings
        self.region = region
        self._reason = "ok"
        self._forecasts: dict[str, tuple[pd.DataFrame, ForecastMeta]] = {}
        self._models: dict[str, dict[str, Any]] = {}
        try:
            load_regions()[region]
            for target in TARGETS:
                metadata = read_metadata(region, target, settings.models_dir)
                model = load_model(region, target, settings.models_dir, metadata["version"])
                if metadata.get("data_source") != "raw":
                    raise ModelIncompatibleError("Serving requires raw-trained models")
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
