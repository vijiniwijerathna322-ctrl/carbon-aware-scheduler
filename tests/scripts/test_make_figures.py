import json
from pathlib import Path
from runpy import run_path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

helpers = run_path(str(Path(__file__).resolve().parents[2] / "scripts/make_figures.py"))


@pytest.fixture
def reports(tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    issue = pd.Timestamp("2024-01-01", tz="UTC")
    horizons = np.arange(1, 49)
    frame = pd.DataFrame(
        {
            "issue_time": issue,
            "target_time": issue + pd.to_timedelta(horizons, unit="h"),
            "horizon": horizons,
            "y": 100.0,
            "median": 99.0,
            "lower": 95.0,
            "upper": 105.0,
        }
    )
    for target in ("demand_mwh", "carbon_intensity_g_per_kwh"):
        for model in ("cqr", "naive"):
            frame.to_parquet(root / f"backtest_CISO_{target}_{model}.parquet", index=False)
    pd.DataFrame(
        {
            "strategy": ["median", "upper"],
            "status": "scored",
            "window_h": 12,
            "savings_pct": [20.0, 15.0],
            "oracle_savings_pct": 25.0,
        }
    ).to_parquet(root / "schedule_backtest_CISO.parquet", index=False)
    (root / "drift_simulation.json").write_text(
        json.dumps({"results": [{"coverage": value} for value in [0.82, 0.78, 0.77, 0.67]]})
    )
    return root, frame


def test_returns_five_existing_png_paths(reports, tmp_path):
    paths = helpers["make_figures"](reports[0], tmp_path / "figures")
    assert len(paths) == 5  # noqa: PLR2004
    assert all(path.read_bytes().startswith(b"\x89PNG") for path in paths)


def test_nominal_line_present_in_coverage_figure(reports):
    figure = helpers["coverage_figure"](
        {target: reports[1] for target in ("demand_mwh", "carbon_intensity_g_per_kwh")}
    )
    for axis in figure.axes:
        assert any(np.array_equal(line.get_ydata(), [80, 80]) for line in axis.lines)
    plt.close(figure)


def test_missing_input_raises_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="run raw backtests"):
        helpers["make_figures"](tmp_path, tmp_path / "out")
