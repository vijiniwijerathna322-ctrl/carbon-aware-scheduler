"""Webhook delivery is best-effort: it reports success/failure and never raises."""

import datetime as dt
import json

import httpx
import respx

from carbon_scheduler.monitoring.notify import post_alert_webhook
from carbon_scheduler.monitoring.report import MonitorReport

URL = "https://hooks.example.com/alert"


def _report() -> MonitorReport:
    now = dt.datetime(2026, 10, 11, 6, tzinfo=dt.UTC)
    return MonitorReport(
        region="CISO",
        generated_at=now,
        model_version={"demand_mwh": "v1"},
        window_start=now,
        window_end=now,
        feature_drift={},
        coverage={},
        mae_ratio={},
        status="alert",
        reasons=["demand_mwh: coverage alert; 120 unique realized hours (minimum 100)."],
        replay={},
        baseline={},
        provenance={},
    )


@respx.mock
def test_webhook_delivers_generic_payload_on_alert():
    route = respx.post(URL).mock(return_value=httpx.Response(200))
    assert post_alert_webhook(_report(), URL) is True
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["status"] == "alert"
    assert body["region"] == "CISO"
    assert "coverage alert" in body["summary"]


@respx.mock
def test_webhook_slack_style_payload_is_text_only():
    route = respx.post(URL).mock(return_value=httpx.Response(200))
    assert post_alert_webhook(_report(), URL, style="slack") is True
    body = json.loads(route.calls.last.request.content)
    assert set(body) == {"text"}


@respx.mock
def test_webhook_failure_is_swallowed_and_reported_false():
    respx.post(URL).mock(return_value=httpx.Response(500))
    assert post_alert_webhook(_report(), URL) is False
