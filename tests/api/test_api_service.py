"""Real small artifact integration and immutable snapshot contract."""

# ruff: noqa: PLR2004

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from carbon_scheduler.api.service import ForecastService, ServiceUnavailableError
from carbon_scheduler.models.registry import read_metadata


def test_service_prediction_and_concurrent_copies(trained_settings):
    service = ForecastService(trained_settings)
    assert service.is_healthy() == (True, "ok")
    demand, demand_meta = service.forecast("demand_mwh", 6)
    _, carbon_meta = service.forecast("carbon_intensity_g_per_kwh")
    assert len(demand) == 6
    assert demand_meta.issue_time - carbon_meta.issue_time == pd.Timedelta(hours=1)
    assert demand_meta.issue_time == demand_meta.data_as_of
    assert demand_meta.model_version
    assert demand_meta.alpha == pytest.approx(0.2)
    demand.loc[:, "median"] = -999
    assert (service.forecast("demand_mwh", 6)[0]["median"] >= 0).all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.forecast("demand_mwh", 6)[0], range(2)))
    pd.testing.assert_frame_equal(*results)
    assert results[0] is not results[1]
    with pytest.raises(ValueError, match="Unknown"):
        service.forecast("unknown")


def test_service_staleness_and_model_metadata(trained_settings):
    service = ForecastService(trained_settings.model_copy(update={"demo_mode": False}))
    assert service.is_healthy() == (False, "data_stale")
    with pytest.raises(ServiceUnavailableError, match="data_stale"):
        service.forecast("demand_mwh")
    with pytest.raises(ServiceUnavailableError):
        service.current_models()


def test_incompatible_factors_fail_closed(trained_settings, monkeypatch):
    def wrong_factors(*args):
        result = read_metadata(*args)
        result["factors_sha256"] = "different"
        return result

    monkeypatch.setattr("carbon_scheduler.api.service.read_metadata", wrong_factors)
    service = ForecastService(trained_settings)
    assert service.is_healthy() == (False, "models_incompatible")
    with pytest.raises(ServiceUnavailableError, match="models_incompatible"):
        service.forecast("demand_mwh")
