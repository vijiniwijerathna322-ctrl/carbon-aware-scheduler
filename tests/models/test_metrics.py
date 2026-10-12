# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.metrics import (
    interval_coverage,
    mae,
    mean_interval_width,
    pinball_loss,
    winkler_score,
)


def test_hand_computed_metrics():
    assert mae([1, 3], [2, 1]) == 1.5
    assert pinball_loss([1, 3], [2, 1], 0.5) == 0.75
    assert pinball_loss([2, 0], [0, 1], 0.9) == pytest.approx(0.95)
    assert interval_coverage([0, 1, 2, 4], [0, 0, 0, 0], [3, 3, 3, 3]) == 0.75
    assert mean_interval_width([0, 1], [2, 5]) == 3.0
    assert winkler_score([-1, 1, 3], [0, 0, 0], [2, 2, 2], 0.2) == pytest.approx(26 / 3)


def test_missing_pairs_and_series_indices_are_ignored_positionally():
    assert mae(pd.Series([1, np.nan, 100], index=[3, 2, 1]), [2, 10, np.nan]) == 1
    assert interval_coverage([1, np.nan, 3], [0, 0, np.nan], [2, 2, 4]) == 1
    assert mean_interval_width([0, np.nan], [2, 4]) == 2


@pytest.mark.parametrize(
    "function,args",
    [
        (mae, ([], [])),
        (pinball_loss, ([], [], 0.5)),
        (interval_coverage, ([], [], [])),
        (mean_interval_width, ([], [])),
        (winkler_score, ([], [], [], 0.2)),
    ],
)
def test_empty_input_returns_nan(function, args):
    assert np.isnan(function(*args))


def test_invalid_shapes_alpha_and_intervals_raise():
    with pytest.raises(ValueError, match="shape"):
        mae([1, 2], [1])
    with pytest.raises(ValueError, match="alpha"):
        pinball_loss([1], [1], 1)
    with pytest.raises(ValueError, match="ordered"):
        winkler_score([1], [2], [0], 0.2)
    with pytest.raises(ValueError, match="finite"):
        mae([np.inf], [1])
