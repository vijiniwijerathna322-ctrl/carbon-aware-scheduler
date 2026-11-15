"""Best-effort alert delivery; never changes the monitor command's exit code."""

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from carbon_scheduler.monitoring.report import MonitorReport

logger = logging.getLogger(__name__)


def _payload(report: MonitorReport, style: str) -> dict[str, Any]:
    summary = (
        f"[{report.status.upper()}] {report.region} monitoring at "
        f"{report.generated_at.isoformat()}: {'; '.join(report.reasons) or 'see report'}"
    )
    if style == "slack":
        return {"text": summary}
    return {
        "status": report.status,
        "region": report.region,
        "generated_at": report.generated_at.isoformat(),
        "model_version": report.model_version,
        "reasons": report.reasons,
        "summary": summary,
    }


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _post(http: httpx.Client, url: str, payload: dict[str, Any]) -> None:
    response = http.post(url, json=payload, timeout=10)
    response.raise_for_status()


def post_alert_webhook(
    report: MonitorReport,
    webhook_url: str,
    *,
    style: str = "generic",
    http: httpx.Client | None = None,
) -> bool:
    """POST the alert verdict; return whether delivery succeeded. Never raises."""
    owns_client = http is None
    client = http or httpx.Client()
    try:
        _post(client, webhook_url, _payload(report, style))
        return True
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Monitor alert webhook delivery failed: %s", error)
        return False
    finally:
        if owns_client:
            client.close()
