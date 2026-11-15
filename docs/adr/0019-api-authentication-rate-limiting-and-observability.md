# ADR 0019: API authentication, rate limiting and observability

## Context

The FastAPI service (`src/carbon_scheduler/api/`) had no authentication, no
rate limiting, no request-level metrics, and never initialized logging in the
API process at all (`configure_logging` was only ever called from the CLI
callback). The offline demo deliberately needs to keep running without any
credential, so any change here had to preserve that, while giving the service
the baseline operational surface a reviewer would expect from a "production"
API: who can call it, how abusive traffic is bounded, and what an operator
can observe.

## Decision

**Authentication.** An optional `X-API-Key` header, checked by
`api/security.py`'s `require_api_key` dependency against the comma-separated
`API_KEYS` setting. An unset/empty `API_KEYS` disables the check entirely —
this is a single-service demo API, not a multi-tenant product, so a bare
API-key header is proportionate; OAuth2/JWT would add complexity with no
corresponding need (no per-user scopes, no third-party clients). `/healthz`,
`/metrics`, `/docs` and `/openapi.json` stay open; every `/v1/*` route (moved
to its own `v1_router` in `api/routes.py`) requires the key when one is
configured.

**Rate limiting.** A hand-rolled in-memory fixed-window counter
(`api/rate_limit.py`'s `FixedWindowRateLimiter`), keyed by the presented API
key when there is one, else by client address, applied globally by
`RateLimitMiddleware` with a default of `RATE_LIMIT_PER_MINUTE` (60)
requests/minute. This started as `slowapi`, the common off-the-shelf choice —
but direct testing (not a changelog read) showed its automatic route
discovery (`SlowAPIMiddleware`, scanning `app.routes` for a matching handler)
never finds routes mounted via `APIRouter.include_router` on this FastAPI
version: `app.routes` holds opaque `_IncludedRouter` entries instead of flat
routes, so the limiter silently never fires (every request kept returning
200). The documented workaround is per-route `@limiter.limit(...)`
decorators, but a ~40-line counter was simpler to reason about, deterministic
to unit-test (inject `now=`), and removed a dependency whose own
compatibility with this FastAPI version was already in question. In-memory
means **this is not safe across multiple process instances** — a real
multi-instance deployment would need a shared store (e.g. Redis-backed).
That's a known, accepted limit for a single-instance free-tier deployment,
not a production multi-tenant guarantee.

**Structured logging + correlation.** `logging.py` now emits one JSON line per
record (UTC timestamp, level, logger, message, `request_id`) instead of plain
text, and the API lifespan now actually calls `configure_logging` — previously
a real gap, since the API process ran with Python's default unconfigured
logging. `api/middleware.py`'s `ObservabilityMiddleware` assigns/propagates an
`X-Request-ID` header, stores it in a `contextvars.ContextVar` the formatter
reads, and logs one access line per request (method, route, status, duration).

**Metrics.** `prometheus-client` counters/histograms (`api/metrics.py`),
labeled by method/route/status, recorded by the same middleware; served
unauthenticated at `GET /metrics` like `/healthz` — pull-based Prometheus
scraping, not a push gateway, since there's a single instance to scrape.

**Alerting.** `monitoring/notify.py` posts the monitor verdict to an optional
`MONITOR_WEBHOOK_URL` (generic JSON or Slack's `{"text": ...}` shape via
`MONITOR_WEBHOOK_STYLE`) only when `monitor`'s computed status is `"alert"`.
It retries transport errors a couple of times (reusing the existing `tenacity`
dependency) but is explicitly **best-effort**: any failure is logged and
returned as `False`, never raised, and never changes the CLI's exit code
(still 2 for `alert`, regardless of whether the notification itself landed).

## Consequences

Local `uv run` development and the keyless offline demo are unaffected: no
`API_KEYS` means no auth check, and the webhook is only ever invoked when a
URL is explicitly configured. Deploying more than one instance behind a load
balancer would need a shared rate-limit store; this is documented here rather
than silently assumed. The webhook has no delivery guarantee and no
dead-letter/retry queue beyond its few in-process retries — acceptable for a
monitoring nice-to-have, not a substitute for a real incident pipeline.
