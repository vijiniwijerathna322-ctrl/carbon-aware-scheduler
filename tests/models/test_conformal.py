# ruff: noqa: PLR2004
import numpy as np
import pytest

from carbon_scheduler.models.conformal import SplitConformalCQR


def test_exchangeable_coverage_over_twenty_seeds():
    coverages = []
    for seed in range(20):
        rng = np.random.default_rng(seed)
        horizon = rng.integers(1, 49, 6000)
        scale = np.where(horizon <= 6, 1.0, np.where(horizon <= 24, 2.0, 3.0))
        y = rng.normal(size=len(horizon)) * scale
        model = SplitConformalCQR().calibrate(-0.3 * scale, 0.3 * scale, y, horizon)
        h = rng.integers(1, 49, 6000)
        s = np.where(h <= 6, 1.0, np.where(h <= 24, 2.0, 3.0))
        actual = rng.normal(size=len(h)) * s
        lo, hi = model.adjust(-0.3 * s, 0.3 * s, h)
        coverages.append(np.mean((actual >= lo) & (actual <= hi)))
    assert 0.78 <= np.mean(coverages) <= 0.82
    assert min(coverages) >= 0.74


def test_finite_sample_rank_and_tiny_sample():
    model = SplitConformalCQR(min_points=1)
    model.calibrate(np.zeros(9), np.zeros(9), np.arange(1, 10), np.ones(9))
    assert model.corrections_[(1, 6)] == 8
    model.calibrate(np.zeros(2), np.zeros(2), np.array([2, 4]), np.ones(2))
    assert model.corrections_[(1, 6)] == 4


def test_negative_correction_cannot_cross_and_constant_target_is_measured(caplog):
    model = SplitConformalCQR(min_points=1)
    model.calibrate(np.full(40, -10.0), np.full(40, 10.0), np.zeros(40), np.ones(40))
    assert model.corrections_[(1, 6)] == -10
    lo, hi = model.adjust(np.array([-1.0]), np.array([1.0]), np.array([1]))
    assert lo.tolist() == hi.tolist() == [0.0]
    assert "constant" in caplog.text


def test_missing_bucket_falls_back_to_pooled(caplog):
    model = SplitConformalCQR().calibrate(np.zeros(40), np.zeros(40), np.arange(40), np.ones(40))
    assert model.corrections_[(7, 24)] == model.pooled_correction_
    assert "pooled" in caplog.text


def test_empty_nonfinite_unfitted_and_bad_shapes_raise():
    with pytest.raises(RuntimeError, match="calibrate"):
        SplitConformalCQR().adjust(np.zeros(1), np.ones(1), np.ones(1))
    with pytest.raises(ValueError, match="finite"):
        SplitConformalCQR().calibrate(np.array([np.nan]), np.ones(1), np.ones(1), np.ones(1))
    with pytest.raises(ValueError, match="shape"):
        SplitConformalCQR().calibrate(np.zeros(2), np.ones(1), np.ones(1), np.ones(1))
    with pytest.raises(ValueError, match="alpha"):
        SplitConformalCQR(alpha=0)
    with pytest.raises(ValueError, match="horizon"):
        SplitConformalCQR().calibrate(np.zeros(1), np.ones(1), np.ones(1), np.array([49]))
