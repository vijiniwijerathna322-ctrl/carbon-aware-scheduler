import json
from pathlib import Path

import httpx
import pytest
import respx

pytest.importorskip("streamlit")
from fastapi.testclient import TestClient  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from carbon_scheduler.api.main import create_app  # noqa: E402
from carbon_scheduler.api.service import ForecastService  # noqa: E402
from carbon_scheduler.config import Settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = json.loads((ROOT / "docs/demo/responses.json").read_text())
URL = "http://127.0.0.1:8000"


def test_dashboard_forecast_schedule_and_missing_report(monkeypatch):
    monkeypatch.setenv("CARBON_API_URL", URL)
    with respx.mock:
        respx.get(f"{URL}/healthz").mock(return_value=httpx.Response(200, json=CAPTURE["health"]))
        respx.get(f"{URL}/v1/forecast").mock(
            return_value=httpx.Response(200, json=CAPTURE["forecast"])
        )
        respx.get(f"{URL}/v1/monitoring/status").mock(
            return_value=httpx.Response(404, json={"error": "no_report"})
        )
        schedule = respx.post(f"{URL}/v1/schedule").mock(
            return_value=httpx.Response(200, json=CAPTURE["schedule"])
        )
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
        assert not app.exception
        assert any("No monitoring report" in item.value for item in app.info)
        next(button for button in app.button if button.label == "Find a window").click().run()
        assert not app.exception
        assert schedule.called
        payload = json.loads(schedule.calls.last.request.content)
        assert payload["deadline"] == "2026-10-12T07:00:00+00:00"
        assert payload["region"] == "CISO"


def test_dashboard_connection_failure_is_actionable(monkeypatch):
    monkeypatch.setenv("CARBON_API_URL", URL)
    with respx.mock:
        respx.get(f"{URL}/healthz").mock(side_effect=httpx.ConnectError("unavailable"))
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
        assert not app.exception
        assert "backend is running" in app.error[0].value


def test_dashboard_against_real_frozen_demo(monkeypatch, tmp_path):
    monkeypatch.setenv("CARBON_API_URL", URL)
    settings = Settings().model_copy(
        update={
            "data_dir": ROOT / "demo/data",
            "models_dir": ROOT / "demo/models",
            "reports_dir": tmp_path,
            "demo_mode": True,
        }
    )
    with TestClient(create_app(lambda: ForecastService(settings))) as backend, respx.mock:

        def proxy(request):
            return backend.request(
                request.method,
                str(request.url).removeprefix(URL),
                content=request.content,
                headers={"content-type": "application/json"},
            )

        respx.route().mock(side_effect=proxy)
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=60)
        assert not app.exception
        assert not app.error
        next(button for button in app.button if button.label == "Find a window").click().run(
            timeout=60
        )
        assert not app.exception
        assert not app.error
        assert any(metric.label == "Expected proxy savings" for metric in app.metric)
