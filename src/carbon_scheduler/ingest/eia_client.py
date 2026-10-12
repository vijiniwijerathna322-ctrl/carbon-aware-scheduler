"""Bounded, paginated EIA requests with secret-safe failures."""

import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from time import monotonic
from time import sleep as default_sleep
from typing import Any

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_random_exponential


class EiaAuthError(RuntimeError):
    """EIA rejected the configured credentials."""


class EiaRequestError(RuntimeError):
    """EIA could not provide a valid complete response."""


class _Retryable(Exception):
    """Transient upstream failure."""


class _QuerySecretFilter(logging.Filter):
    secrets: set[str] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(
            r"(api_key(?:=|%3D))[^&\s\"']+",
            r"\1[REDACTED]",
            record.getMessage(),
            flags=re.IGNORECASE,
        )
        for secret in self.secrets:
            record.msg = record.msg.replace(secret, "[REDACTED]")
        if record.exc_info is not None:
            detail = logging.Formatter().formatException(record.exc_info)
            for secret in self.secrets:
                detail = detail.replace(secret, "[REDACTED]")
            record.exc_text = detail
            record.exc_info = None
        record.args = ()
        return True


# httpx logs the request URL at INFO, including query credentials. Redact only
# this credential parameter; other requests and their log messages remain visible.
logging.getLogger("httpx").addFilter(_QuerySecretFilter())


class EiaClient:
    """Fetch complete EIA routes; injected HTTP clients remain caller-owned."""

    def __init__(  # noqa: PLR0913
        self,
        api_key: str,
        *,
        base_url: str = "https://api.eia.gov/v2",
        http: httpx.Client | None = None,
        page_length: int = 5000,
        min_interval_s: float = 0.25,
        max_retries: int = 5,
        sleep: Callable[[float], None] = default_sleep,
    ) -> None:
        if not 1 <= page_length <= 5000:  # noqa: PLR2004
            raise ValueError("page_length must be between 1 and 5000")
        if max_retries < 0 or not math.isfinite(min_interval_s) or min_interval_s < 0:
            raise ValueError("Retry count and request interval must be nonnegative")
        if api_key:
            _QuerySecretFilter.secrets.add(api_key)
        self._key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = (
            http
            if http is not None
            else httpx.Client(timeout=httpx.Timeout(connect=30, read=90, write=30, pool=30))
        )
        for name in tuple(logging.Logger.manager.loggerDict):
            if name.startswith("httpcore"):
                logger = logging.getLogger(name)
                if not any(isinstance(item, _QuerySecretFilter) for item in logger.filters):
                    logger.addFilter(_QuerySecretFilter())
        self._owns_http = http is None
        self._page_length = page_length
        self._interval = min_interval_s
        self._retries = max_retries
        self._sleep = sleep
        self._last_request: float | None = None

    def __enter__(self) -> "EiaClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close only the transport created by this client."""
        if self._owns_http:
            self._http.close()

    def _request(self, route: str, params: list[tuple[str, str]]) -> httpx.Response:
        if self._last_request is not None:
            delay = self._interval - (monotonic() - self._last_request)
            if delay > 0:
                self._sleep(delay)
        self._last_request = monotonic()
        try:
            response = self._http.get(
                f"{self._base_url}/{route.strip('/')}/data/",
                params=httpx.QueryParams(tuple(params)),
            )
        except httpx.TransportError:
            if self._owns_http:
                self._http.close()
                self._http = httpx.Client(
                    timeout=httpx.Timeout(connect=30, read=90, write=30, pool=30)
                )
            raise _Retryable("EIA transport failed") from None
        if response.status_code in (401, 403):
            raise EiaAuthError("EIA rejected the API key")
        if response.status_code == 429 or 500 <= response.status_code < 600:  # noqa: PLR2004
            raise _Retryable("EIA temporarily unavailable")
        if not response.is_success:
            raise EiaRequestError(f"EIA request failed (HTTP {response.status_code})")
        return response

    def fetch_route(  # noqa: PLR0913
        self,
        route: str,
        *,
        facets: Mapping[str, Sequence[str]],
        start: str,
        end: str,
        data: Sequence[str] = ("value",),
        frequency: str = "hourly",
    ) -> list[dict[str, Any]]:
        """Return all rows, rejecting incomplete or malformed pagination."""
        params = [
            ("api_key", self._key),
            ("frequency", frequency),
            ("start", start),
            ("end", end),
            ("length", str(self._page_length)),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
        ]
        category = {
            "electricity/rto/region-data": "type",
            "electricity/rto/fuel-type-data": "fueltype",
        }.get(route.strip("/"))
        if category is not None:
            params.extend(
                [
                    ("sort[1][column]", "respondent"),
                    ("sort[1][direction]", "asc"),
                    ("sort[2][column]", category),
                    ("sort[2][direction]", "asc"),
                ]
            )
        params.extend((f"data[{i}]", value) for i, value in enumerate(data))
        params.extend(
            (f"facets[{name}][]", value) for name, values in facets.items() for value in values
        )
        rows: list[dict[str, Any]] = []
        while True:
            retry = Retrying(
                retry=retry_if_exception_type(_Retryable),
                stop=stop_after_attempt(self._retries + 1),
                wait=wait_random_exponential(multiplier=0.5, max=30),
                sleep=self._sleep,
                reraise=True,
            )
            try:
                response = retry(self._request, route, [*params, ("offset", str(len(rows)))])
            except _Retryable:
                raise EiaRequestError("EIA request failed after bounded retries") from None
            try:
                payload = response.json()["response"]
                total_raw = payload["total"]
                if isinstance(total_raw, bool) or not isinstance(total_raw, (str, int)):
                    raise ValueError
                total = int(total_raw)
                page = payload["data"]
                if (
                    total < 0
                    or not isinstance(page, list)
                    or not all(isinstance(row, dict) for row in page)
                ):
                    raise ValueError
                if len(page) > self._page_length or len(rows) + len(page) > total:
                    raise ValueError
                if not page and len(rows) < total:
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise EiaRequestError("EIA returned malformed or incomplete pagination") from None
            rows.extend(page)
            if len(rows) >= total:
                return rows
