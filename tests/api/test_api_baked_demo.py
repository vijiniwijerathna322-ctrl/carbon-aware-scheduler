"""Exercise the tracked real artifacts on every supported CI platform."""

import hashlib
import json

from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastService
from carbon_scheduler.config import PROJECT_ROOT, Settings


def test_baked_demo_offline_forecast_and_schedule(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    root = PROJECT_ROOT / "demo"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    metadata_path = next((root / "models/CISO/carbon_intensity_g_per_kwh").rglob("metadata.json"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert (
        hashlib.sha256((PROJECT_ROOT / "config/emission_factors.yaml").read_bytes()).hexdigest()
        == metadata["factors_sha256"]
    )
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    settings = Settings(
        _env_file=None, data_dir=root / "data", models_dir=root / "models", demo_mode=True
    )
    with TestClient(create_app(lambda: ForecastService(settings))) as client:
        response = client.get("/healthz")
        assert response.is_success, response.text
        for target in ("demand_mwh", "carbon_intensity_g_per_kwh"):
            response = client.get("/v1/forecast", params={"target": target, "horizon": 6})
            assert response.is_success, response.text
            assert len(response.json()["points"]) == 6  # noqa: PLR2004
        response = client.post(
            "/v1/schedule",
            json={"duration_hours": 2, "power_kw": 7, "deadline": "2026-10-12T06:00:00Z"},
        )
        assert response.is_success, response.text
        assert response.json()["recommendation"]["end"] <= "2026-10-12T06:00:00Z"
        assert response.json()["notes"]
        models = client.get("/v1/models/current").json()["models"]
        for metadata in models.values():
            assert metadata["fit_end"].endswith("Z")
            assert metadata["trained_at"].endswith("Z")
