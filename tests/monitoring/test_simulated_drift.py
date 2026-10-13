"""A real tiny fitted model detects post-fit intensity shifts through coverage."""

# ruff: noqa: PLR2004
import json
from unittest.mock import patch

import numpy as np
import pandas as pd

from carbon_scheduler.config import Settings
from carbon_scheduler.ingest.store import write_hourly
from carbon_scheduler.models.backtest import BacktestConfig
from carbon_scheduler.models.registry import load_model, read_metadata
from carbon_scheduler.models.reporting import TARGETS, load_backtest_series
from carbon_scheduler.models.training import train_region
from carbon_scheduler.monitoring import report as module


def test_real_fitted_model_coverage_detects_shift_within_seven_days(tmp_path):
    rng = np.random.default_rng(42)
    index = pd.date_range(
        "2024-01-01", periods=240 * 24, freq="h", tz="UTC", name="period"
    ).as_unit("ns")
    frame = pd.DataFrame(
        {
            "demand_mwh": 100
            + 6 * np.sin(np.arange(len(index)) * 2 * np.pi / 24)
            + np.resize(rng.normal(0, 0.4, 168), len(index)),
            "gen_ng_mwh": 50 + np.resize(rng.normal(0, 0.5, 168), len(index)),
            "gen_nuc_mwh": 50.0,
        },
        index=index,
    )
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        reports_dir=tmp_path / "reports",
    )
    write_hourly(frame, "CISO", "raw", settings.data_dir)
    fit_end = index[-1] - pd.Timedelta(days=35)
    train_region("CISO", settings, fit_end=fit_end, lgbm_params={"n_estimators": 20})
    settings.reports_dir.mkdir()
    start = index[-1] - pd.Timedelta(days=14) + pd.Timedelta(hours=1)
    for target in TARGETS:
        series, provenance = load_backtest_series("CISO", target, settings)
        metadata = read_metadata("CISO", target, settings.models_dir)
        model = load_model("CISO", target, settings.models_dir)
        baseline, _ = module._replay(
            series,
            model,
            BacktestConfig(
                fit_end + pd.Timedelta(hours=1), start - pd.Timedelta(hours=1), metadata["tz"]
            ),
            fit_end,
        )
        path = settings.reports_dir / f"backtest_CISO_{target}_cqr.parquet"
        baseline.to_parquet(path, index=False)
        params = {
            **metadata["lgbm_parameters"],
            "seed": metadata["seed"],
            "n_jobs": 1,
            "issue_step_h": metadata["issue_step_h"],
        }
        path.with_suffix(".json").write_text(
            json.dumps(
                {
                    **provenance,
                    "timezone": metadata["tz"],
                    "calibration_days": 90,
                    "model_parameters": json.dumps(params),
                }
            ),
            encoding="utf-8",
        )
    before = module.build_monitor_report("CISO", settings, index[-1].to_pydatetime())
    assert before.coverage[TARGETS[1]].status == "ok"
    assert before.status == "ok", before.reasons

    def shifted_loader(region, target, config):
        series, provenance = load_backtest_series(region, target, config)
        if target == TARGETS[1]:
            series.iloc[-7 * 24 :] *= 1.3
        return series, provenance

    with patch.object(module, "load_backtest_series", side_effect=shifted_loader):
        after = module.build_monitor_report("CISO", settings, index[-1].to_pydatetime())
    assert after.coverage[TARGETS[1]].n >= 100
    assert after.coverage[TARGETS[1]].status == "alert"
    assert after.status == "alert"
