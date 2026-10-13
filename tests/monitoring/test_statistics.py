"""Distribution changes, missing data and coverage decision boundaries."""

# ruff: noqa: PLR2004
import numpy as np
import pytest

from carbon_scheduler.monitoring.drift import classify_psi, ks_drift, psi
from carbon_scheduler.monitoring.performance import coverage_status, mae_ratio_status


def test_psi_identical_shift_and_nan():
    rng = np.random.default_rng(42)
    reference = rng.normal(size=2000)
    assert psi(reference, reference) == 0
    assert psi(reference, reference + 2) > 0.25
    assert psi(np.append(reference, np.nan), reference) == 0
    assert psi(np.ones(100), np.ones(100)) == 0
    assert psi(np.ones(100), np.ones(100) * 2) > 0.25
    assert psi(np.tile([0.0, 1.0], 50), np.ones(100)) > 0.25
    with pytest.raises(ValueError, match="finite"):
        psi(np.array([np.nan]), reference)
    with pytest.raises(ValueError):
        psi(np.array([np.inf]), reference)


def test_ks_detects_shift_with_few_false_alarms():
    false_alarms = 0
    for seed in range(20):
        rng = np.random.default_rng(seed)
        reference, current = rng.normal(size=(2, 1000))
        false_alarms += ks_drift(reference, current)[1] < 0.01
        assert ks_drift(reference, current + 2)[1] < 0.01
    assert false_alarms <= 1


@pytest.mark.parametrize("value,status", [(0, "ok"), (0.1, "warn"), (0.25, "alert")])
def test_psi_thresholds(value, status):
    assert classify_psi(value) == status


def test_coverage_calibrated_undercoverage_and_single_outlier():
    y = np.zeros(2000)
    y[1600:] = 2
    assert coverage_status(y, np.zeros(2000), np.ones(2000)).status == "ok"
    y[1200:] = 2
    assert coverage_status(y, np.zeros(2000), np.ones(2000)).status == "alert"
    y[:] = 0
    y[1600:] = 2
    y[0] = 2
    assert coverage_status(y, np.zeros(2000), np.ones(2000)).status == "ok"


def test_missing_pairs_and_insufficient_coverage():
    result = coverage_status(np.array([0.0, np.nan]), np.zeros(2), np.ones(2))
    assert result.n == 1 and result.status == "insufficient_data"
    assert result.coverage == 1 and result.p_value is None
    result = coverage_status(np.array([]), np.array([]), np.array([]))
    assert result.coverage is None
    with pytest.raises(ValueError):
        coverage_status(np.zeros(2), np.ones(2), np.zeros(2))


@pytest.mark.parametrize(
    "recent,baseline,status",
    [(1, 1, "ok"), (1.5, 1, "warn"), (2, 1, "alert"), (0, 0, "ok"), (1, 0, "alert")],
)
def test_mae_ratio_thresholds(recent, baseline, status):
    assert mae_ratio_status(recent, baseline) == status
