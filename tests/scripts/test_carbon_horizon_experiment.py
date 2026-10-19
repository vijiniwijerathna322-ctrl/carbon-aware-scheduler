import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    "carbon_horizon_experiment",
    Path(__file__).resolve().parents[2] / "scripts/experiment_carbon_horizons.py",
)
assert spec and spec.loader
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def forecast_frame():
    return pd.DataFrame(
        {
            "issue_time": [experiment.START] * 48,
            "target_time": pd.date_range(
                experiment.START + pd.Timedelta(hours=1), periods=48, freq="h"
            ),
            "horizon": range(1, 49),
            "y": np.ones(48),
            "median": np.ones(48),
            "lower": np.zeros(48),
            "upper": np.full(48, 2.0),
        }
    )


def test_experiment_excludes_future_history(monkeypatch, tmp_path):
    seen = []

    def backtest(history, factory, cfg):
        assert history.index.max() == experiment.END
        assert cfg.test_end == experiment.END
        model = factory()
        seen.append(len(model.calibrator.buckets))
        assert model.calibration_days == 90  # noqa: PLR2004
        return forecast_frame()

    monkeypatch.setattr(experiment, "rolling_origin_backtest", backtest)
    series = pd.Series([1.0, 999.0], index=[experiment.END, pd.Timestamp("2026-10-19T00:00Z")])
    result = experiment.compare_variants(series, {}, tmp_path)
    assert seen == [3, 48]
    assert set(result["variants"]) == {"bucket", "per_horizon"}


def test_experiment_rejects_changed_point_model(monkeypatch, tmp_path):
    calls = 0

    def backtest(*args):
        nonlocal calls
        frame = forecast_frame()
        frame["median"] += calls
        calls += 1
        return frame

    monkeypatch.setattr(experiment, "rolling_origin_backtest", backtest)
    with pytest.raises(ValueError, match="identical median"):
        experiment.compare_variants(pd.Series([1], index=[experiment.END]), {}, tmp_path)
    assert not (tmp_path / "comparison.json").exists()
