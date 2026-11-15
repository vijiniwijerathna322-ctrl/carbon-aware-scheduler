"""Prometheus request metrics for the API process."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "carbon_api_requests_total",
    "Total HTTP requests handled by the API.",
    ["method", "route", "status"],
)
REQUEST_LATENCY = Histogram(
    "carbon_api_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "route"],
)


def render_latest() -> tuple[bytes, str]:
    """Current metrics in the Prometheus text exposition format."""
    return generate_latest(), CONTENT_TYPE_LATEST
