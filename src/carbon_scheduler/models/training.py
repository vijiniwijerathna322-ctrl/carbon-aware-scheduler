"""Train raw-target CQR models and verify their versioned artifact roundtrip."""

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from carbon_scheduler.config import Settings
from carbon_scheduler.models.base import utc_hour
from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.registry import load_model, save_model
from carbon_scheduler.models.reporting import TARGETS, load_backtest_series
from carbon_scheduler.regions import load_regions

logger = logging.getLogger(__name__)


def train_region(
    region: str,
    settings: Settings,
    targets: Sequence[str] = TARGETS,
    fit_end: pd.Timestamp | None = None,
    *,
    lgbm_params: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    """Fit with 90 held-aside calibration days, preserving pointwise raw gaps.

    Calibration summaries reuse data that selected corrections and therefore
    cannot certify held-out interval coverage. Overrides support small tests;
    the CLI trains with the documented full default parameters.
    """
    tz = load_regions(settings.regions_path)[region].timezone
    if not targets or len(set(targets)) != len(targets) or set(targets) - set(TARGETS):
        raise ValueError("targets must be distinct supported forecast targets")
    paths = {}
    for target in targets:
        series, provenance = load_backtest_series(region, target, settings)
        latest = series.last_valid_index()
        if not isinstance(latest, pd.Timestamp):
            raise ValueError("Need finite target observations with timestamp index")
        end = utc_hour(fit_end) if fit_end is not None else latest
        if end > series.index[-1] or end < series.index[0]:
            raise ValueError("fit_end must lie within observed history")
        logger.info("Training %s/%s through %s", region, target, end.isoformat())
        model = ForecastModel(target, tz, lgbm_params=lgbm_params)
        model.fit(series, end)
        model.metadata_.update(provenance)
        metrics = {
            "scope": "reused calibration window; not held-out",
            "calibration": model.calibration_summary().to_dict(orient="index"),
        }
        path = save_model(
            model, region, settings.models_dir, metrics, regions_path=settings.regions_path
        )
        loaded = load_model(
            region,
            target,
            settings.models_dir,
            version=path.name,
            regions_path=settings.regions_path,
        )
        pd.testing.assert_frame_equal(model.predict(series, end), loaded.predict(series, end))
        logger.info("Saved %s; identical reloaded predictions verified", path)
        paths[target] = path
    return paths
