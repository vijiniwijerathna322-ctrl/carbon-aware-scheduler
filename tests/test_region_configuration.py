from unittest.mock import Mock
from zoneinfo import ZoneInfoNotFoundError

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.carbon.dataset import build_dataset
from carbon_scheduler.config import Settings
from carbon_scheduler.ingest.pipeline import run_ingest
from carbon_scheduler.ingest.store import read_hourly, write_hourly
from carbon_scheduler.models.training import train_region
from carbon_scheduler.monitoring.report import build_monitor_report, write_monitor_report
from carbon_scheduler.regions import UnknownRegionError, load_regions


def test_load_regions_validates_timezone(tmp_path):
    path = tmp_path / "regions.yaml"
    path.write_text("TEST: {timezone: Invalid/Timezone, lat: 0, lon: 0}", encoding="utf-8")
    with pytest.raises(ZoneInfoNotFoundError):
        load_regions(path)


def test_unknown_region_error_lists_known_codes(tmp_path):
    path = tmp_path / "regions.yaml"
    path.write_text("TEST: {timezone: UTC, lat: 0, lon: 0}", encoding="utf-8")
    with pytest.raises(UnknownRegionError, match="choose from TEST"):
        load_regions(path)["MISSING"]


def test_regions_path_environment(monkeypatch, tmp_path):
    path = tmp_path / "regions.yaml"
    monkeypatch.setenv("CARBON_REGIONS_PATH", str(path))
    assert Settings(_env_file=None).regions_path == path


def test_pipeline_runs_for_synthetic_region_defined_only_in_temp_yaml(tmp_path):
    path = tmp_path / "regions.yaml"
    path.write_text("TEST: {timezone: UTC, lat: 0, lon: 0}", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        regions_path=path,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        reports_dir=tmp_path / "reports",
        demo_mode=True,
    )
    index = pd.date_range(
        "2024-01-01", periods=150 * 24, freq="h", tz="UTC", name="period"
    ).as_unit("ns")
    frame = pd.DataFrame(
        {
            "demand_mwh": 100 + np.arange(len(index)) % 24,
            "gen_ng_mwh": 50 + np.arange(len(index)) % 24,
            "gen_nuc_mwh": 50.0,
        },
        index=index,
    )
    for stage in ("raw", "interim"):
        write_hourly(frame, "TEST", stage, settings.data_dir, regions_path=path)
    processed = build_dataset("TEST", settings)
    assert processed.is_file()
    assert "carbon_intensity_g_per_kwh" in read_hourly(
        "TEST", "processed", settings.data_dir, regions_path=path
    )
    artifacts = train_region("TEST", settings, lgbm_params={"n_estimators": 5})
    assert len(artifacts) == 2  # noqa: PLR2004
    service = ForecastService(settings, region="TEST")
    assert service.is_healthy() == (True, "ok")
    with TestClient(create_app(lambda: service)) as client:
        response = client.get("/v1/forecast?horizon=6")
        assert response.status_code == 200  # noqa: PLR2004
        assert response.json()["region"] == "TEST"
        assert client.get("/v1/forecast?region=ERCO").status_code == 404  # noqa: PLR2004
    report = build_monitor_report("TEST", settings, now=index[-1].to_pydatetime())
    assert report.region == "TEST"
    assert write_monitor_report(report, settings.reports_dir, regions_path=path).is_file()
    with TestClient(create_app(lambda: service)) as client:
        response = client.get("/v1/monitoring/status")
        assert response.status_code == 200  # noqa: PLR2004
        assert response.json()["region"] == "TEST"


def test_erco_timezone():
    assert load_regions()["ERCO"].timezone == "America/Chicago"


def test_ingest_uses_custom_region_config(tmp_path):
    path = tmp_path / "regions.yaml"
    path.write_text("TEST: {timezone: UTC, lat: 0, lon: 0}", encoding="utf-8")
    settings = Settings(_env_file=None, regions_path=path, data_dir=tmp_path / "data")
    client = Mock()

    def fetch(route, *, start, end, **kwargs):
        assert kwargs["facets"]["respondent"] == ["TEST"]
        category = "type" if route.endswith("region-data") else "fueltype"
        codes = ["D", "DF", "NG", "TI"] if category == "type" else ["NG"]
        return [
            {"period": hour.strftime("%Y-%m-%dT%H"), category: code, "value": "100"}
            for hour in pd.date_range(start, end, freq="h")
            for code in codes
        ]

    client.fetch_route.side_effect = fetch
    report = run_ingest("TEST", "2024-01-01T00", "2024-01-01T03", settings, client)
    assert report.n_rows == 4  # noqa: PLR2004
    assert read_hourly("TEST", "raw", settings.data_dir, regions_path=path).shape[0] == 4  # noqa: PLR2004
