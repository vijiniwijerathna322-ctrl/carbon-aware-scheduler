"""The /v1/forecast/explain endpoint exposes ranked feature contributions."""

# ruff: noqa: PLR2004

from fastapi.testclient import TestClient

from carbon_scheduler.api.main import create_app
from carbon_scheduler.api.service import ForecastService


def test_explain_endpoint_returns_ranked_contributions(trained_settings):
    with TestClient(create_app(lambda: ForecastService(trained_settings))) as client:
        response = client.get("/v1/forecast/explain?horizon=1&top_n=2")
        assert response.status_code == 200
        body = response.json()
        assert body["model_version"]
        assert len(body["points"]) == 1
        point = body["points"][0]
        assert point["horizon"] == 1
        assert len(point["contributions"]) == 2
        magnitudes = [abs(c["contribution"]) for c in point["contributions"]]
        assert magnitudes == sorted(magnitudes, reverse=True)
        assert any("conformal calibration" in note for note in body["notes"])


def test_explain_unknown_target_is_422(trained_settings):
    with TestClient(create_app(lambda: ForecastService(trained_settings))) as client:
        assert client.get("/v1/forecast/explain?target=unknown").status_code == 422


def test_explain_unknown_region_is_404(trained_settings):
    with TestClient(create_app(lambda: ForecastService(trained_settings))) as client:
        assert client.get("/v1/forecast/explain?region=ERCO").status_code == 404
