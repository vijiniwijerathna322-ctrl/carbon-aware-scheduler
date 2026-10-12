# ruff: noqa: PLR2004
import logging
import subprocess
import sys

import httpx
import pytest
import respx

from carbon_scheduler.ingest.eia_client import EiaAuthError, EiaClient, EiaRequestError

URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
KEY = "private-test-key"


def client(**kwargs):
    return EiaClient(KEY, min_interval_s=0, sleep=lambda _: None, **kwargs)


def fetch(c):
    return c.fetch_route(
        "electricity/rto/region-data",
        facets={"respondent": ["CISO"]},
        start="2024-01-01T00",
        end="2024-01-02T00",
    )


@respx.mock
def test_paginates_until_total():
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json={"response": {"total": "12000", "data": [{}] * n}})
            for n in (5000, 5000, 2000)
        ]
    )
    with client() as c:
        assert len(fetch(c)) == 12000
    assert [call.request.url.params["offset"] for call in route.calls] == ["0", "5000", "10000"]


@respx.mock
def test_retries_on_429_then_succeeds():
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json={"response": {"total": "1", "data": [{}]}}),
        ]
    )
    with client() as c:
        assert fetch(c) == [{}]
    assert route.call_count == 2


@respx.mock
def test_gives_up_after_max_retries():
    route = respx.get(URL).respond(503)
    with client(max_retries=2) as c, pytest.raises(EiaRequestError):
        fetch(c)
    assert route.call_count == 3


@respx.mock
def test_invalid_key_raises_auth_error_without_retry(caplog):
    caplog.set_level(logging.DEBUG)
    route = respx.get(URL).respond(403)
    with client() as c, pytest.raises(EiaAuthError) as error:
        fetch(c)
    assert route.call_count == 1
    assert KEY not in str(error.value)
    assert KEY not in caplog.text


@respx.mock
def test_api_key_never_logged(caplog):
    caplog.set_level(logging.DEBUG)
    respx.get(URL).mock(side_effect=httpx.ConnectError(f"failure {KEY}"))
    with client(max_retries=0) as c, pytest.raises(EiaRequestError) as error:
        fetch(c)
    assert KEY not in str(error.value)
    assert KEY not in caplog.text


@respx.mock
def test_empty_page_with_remaining_total_fails():
    respx.get(URL).respond(200, json={"response": {"total": "1", "data": []}})
    with client() as c, pytest.raises(EiaRequestError):
        fetch(c)


@pytest.mark.parametrize(
    "kwargs",
    [{"page_length": 5001}, {"page_length": 0}, {"max_retries": -1}, {"min_interval_s": -1}],
)
def test_invalid_bounds(kwargs):
    with pytest.raises(ValueError):
        EiaClient(KEY, **kwargs)


@respx.mock
def test_throttle_applies_to_retry_attempts(monkeypatch):
    ticks = iter([10.0, 10.1, 10.25])
    monkeypatch.setattr("carbon_scheduler.ingest.eia_client.monotonic", lambda: next(ticks))
    delays = []
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json={"response": {"total": "0", "data": []}}),
        ]
    )
    with EiaClient(KEY, min_interval_s=0.25, sleep=delays.append) as c:
        assert fetch(c) == []
    assert delays[-1] == pytest.approx(0.15)


def test_injected_transport_remains_open():
    with httpx.Client() as http:
        with client(http=http):
            pass
        assert not http.is_closed


@respx.mock
def test_other_httpx_requests_remain_logged(caplog):
    caplog.set_level(logging.DEBUG)
    respx.get(URL).respond(200, json={"response": {"total": "0", "data": []}})
    respx.get("https://example.com/public").respond(200)
    with client() as c:
        fetch(c)
    httpx.get("https://example.com/public")
    assert "https://example.com/public" in caplog.text
    assert KEY not in caplog.text


@respx.mock
@pytest.mark.parametrize(
    "payload",
    [
        {"total": "bad", "data": []},
        {"total": 1, "data": ["bad"]},
        {"total": True, "data": []},
        {"data": []},
    ],
)
def test_malformed_payload_is_safe(payload):
    respx.get(URL).respond(200, json={"response": payload})
    with client() as c, pytest.raises(EiaRequestError):
        fetch(c)


def test_transport_debug_traceback_redacts_key(caplog):
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger("httpcore.connection")

    def fail(request):
        try:
            raise RuntimeError(f"transport detail {KEY}")
        except RuntimeError:
            logger.debug("failed %s", KEY, exc_info=True)
        raise httpx.ConnectError(f"failed {KEY}")

    with (
        httpx.Client(transport=httpx.MockTransport(fail)) as http,
        client(http=http, max_retries=0) as c,
        pytest.raises(EiaRequestError),
    ):
        fetch(c)
    assert "transport detail" in caplog.text
    assert KEY not in caplog.text


@respx.mock
@pytest.mark.parametrize(
    "route,category", [("region-data", "type"), ("fuel-type-data", "fueltype")]
)
def test_known_routes_use_deterministic_category_sort(route, category):
    endpoint = respx.get(f"https://api.eia.gov/v2/electricity/rto/{route}/data/").respond(
        200, json={"response": {"total": "0", "data": []}}
    )
    with client() as c:
        c.fetch_route(
            f"electricity/rto/{route}",
            facets={"respondent": ["CISO"]},
            start="2024-01-01T00",
            end="2024-01-02T00",
        )
    params = endpoint.calls[0].request.url.params
    assert params["sort[1][column]"] == "respondent"
    assert params["sort[2][column]"] == category


def test_fresh_default_client_redacts_lazy_transport_logs():
    script = """
import io
import logging
from carbon_scheduler.ingest.eia_client import EiaClient
stream = io.StringIO()
handler = logging.StreamHandler(stream)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG)
with EiaClient("fresh-secret-key"):
    names = [name for name in logging.Logger.manager.loggerDict if name.startswith("httpcore.")]
    assert names
    for name in names:
        try:
            raise RuntimeError("fresh-secret-key")
        except RuntimeError:
            logging.getLogger(name).debug("failed fresh-secret-key", exc_info=True)
assert "fresh-secret-key" not in stream.getvalue()
assert "[REDACTED]" in stream.getvalue()
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
