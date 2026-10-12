# ruff: noqa: PLR2004
import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.features.build import build_supervised
from carbon_scheduler.models.lgbm import LgbmForecaster, QuantileLgbm
from carbon_scheduler.models.metrics import mae


@pytest.fixture(scope="module")
def sinusoid():
    rng = np.random.default_rng(42)
    hours = np.arange(120 * 24)
    return pd.Series(
        100 + 25 * np.sin(2 * np.pi * hours / 24) + rng.normal(0, 2, len(hours)),
        index=pd.date_range("2024-01-01", periods=len(hours), freq="h", tz="UTC"),
    )


def test_quantiles_ordered_deterministic_and_beat_constant(sinusoid):
    train = build_supervised(sinusoid, sinusoid.index[168:2000:12], tz="UTC")
    test = build_supervised(sinusoid, sinusoid.index[2100:2400:24], tz="UTC")
    params = {"n_estimators": 50, "min_child_samples": 20}
    first = QuantileLgbm(params=params).fit(train, train.y)
    second = QuantileLgbm(params=params).fit(train, train.y)
    pred = first.predict(test)
    pd.testing.assert_frame_equal(pred, second.predict(test))
    assert (pred.q10 <= pred.q50).all()
    assert (pred.q50 <= pred.q90).all()
    assert mae(test.y, pred.q50) < mae(test.y, np.full(len(test), train.y.mean()))


def test_training_physically_truncates_and_excludes_late_targets(sinusoid, monkeypatch):
    seen = []
    original = QuantileLgbm.fit

    def spy(self, X, y):
        seen.append(X.copy())
        return original(self, X, y)

    monkeypatch.setattr(QuantileLgbm, "fit", spy)
    end = sinusoid.index[2000]
    dirty_future = sinusoid.copy()
    dirty_future.iloc[100] = np.nan
    dirty_future.loc[dirty_future.index > end] = 1e12
    model = LgbmForecaster("UTC", params={"n_estimators": 10})
    model.fit(dirty_future, end)
    assert seen[0].target_time.max() <= end
    assert seen[0].issue_time.max() <= end
    assert seen[0].y.max() < 200
    assert np.isfinite(seen[0].y).all()
    pred = model.predict(sinusoid.loc[:end], end)
    assert len(pred) == 48
    assert list(pred) == ["target_time", "horizon", "lower", "median", "upper"]
    pd.testing.assert_frame_equal(pred, model.predict(dirty_future, end))


def test_nan_features_still_produce_all_horizons(sinusoid):
    end = sinusoid.index[2000]
    model = LgbmForecaster("UTC", params={"n_estimators": 10})
    model.fit(sinusoid, end)
    missing = sinusoid.loc[:end].copy()
    missing.iloc[-24:] = np.nan
    assert np.isfinite(model.predict(missing, end)[["lower", "median", "upper"]]).all().all()


def test_crossing_quantiles_are_repaired(monkeypatch):
    class Fake:
        def predict(self, X):
            return np.full(len(X), self.value)

    model = QuantileLgbm()
    model.models_ = []
    for value in (3, 1, 2):
        fake = Fake()
        fake.value = value
        model.models_.append(fake)
    data = pd.DataFrame({"horizon": [1]})
    # Stub selection lets this test isolate the crossing repair itself.
    monkeypatch.setattr(model, "_features", lambda X: X)
    assert model.predict(data).iloc[0].tolist() == [1, 2, 3]


def test_invalid_or_unfitted_model_raises(sinusoid):
    with pytest.raises(ValueError, match="quantiles"):
        QuantileLgbm(alphas=(0.2, 0.5, 0.8))
    with pytest.raises(ValueError, match="issue_step"):
        LgbmForecaster("UTC", issue_step_h=0)
    with pytest.raises(RuntimeError, match="fit"):
        LgbmForecaster("UTC").predict(sinusoid, sinusoid.index[-1])
    with pytest.raises(ValueError, match="training"):
        LgbmForecaster("UTC").fit(sinusoid.iloc[:1], sinusoid.index[0])
