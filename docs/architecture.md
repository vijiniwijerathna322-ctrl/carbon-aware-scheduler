# Architecture

This expands the small diagram in the README with the full request path,
including the API hardening and explainability work from
[ADR 0019](adr/0019-api-authentication-rate-limiting-and-observability.md) and
[ADR 0020](adr/0020-model-explainability.md).

```mermaid
flowchart TB
    subgraph Offline pipeline
        EIA[EIA hourly observations] --> RAW[Atomic raw snapshots]
        RAW --> FEAT[Issue-time features]
        FEAT --> TRAIN[LightGBM quantile models]
        TRAIN --> CAL[Split conformal calibration]
        CAL --> REG[Versioned local model registry]
        RAW --> REPLAY[Chronological held-out replay]
        REG --> MON[Drift + coverage monitoring]
        REPLAY --> MON
    end

    subgraph API service
        REG --> SVC[ForecastService: loads current artifacts once]
        SVC --> FC["/v1/forecast"]
        SVC --> EXP["/v1/forecast/explain (LightGBM pred_contrib)"]
        SVC --> SCH["/v1/schedule (deadline-constrained optimizer)"]
        MON --> STATUS["/v1/monitoring/status"]
        AUTH["X-API-Key, optional"] -.->|guards| FC
        AUTH -.->|guards| EXP
        AUTH -.->|guards| SCH
        RL[Fixed-window rate limiter] -.->|wraps| FC
        RL -.->|wraps| EXP
        RL -.->|wraps| SCH
        OBS["Request-ID + JSON access logs + Prometheus"] -.->|instruments| FC
        OBS -.->|instruments| EXP
        OBS -.->|instruments| SCH
        METRICS["/metrics"]
        HEALTH["/healthz"]
    end

    MON -->|alert| WEBHOOK["Optional webhook: best-effort, never blocks CLI exit code"]

    subgraph Clients
        DASH[Streamlit dashboard] -->|HTTP via CARBON_API_URL| FC
        DASH --> EXP
        DASH --> SCH
        DASH --> STATUS
        CURL[curl / API consumer] --> FC
        CURL --> EXP
        CURL --> SCH
    end

    subgraph Deployment target
        DOCKER[Non-root, read-only Docker image] --> RENDER[Render free Docker web service]
        DASH -.->|deployed separately to| STCLOUD[Streamlit Community Cloud]
        RENDER -.->|CARBON_API_URL| STCLOUD
    end
```

## Request path (one call)

1. Client sends `GET /v1/forecast?region=CISO&horizon=6` (or `/explain`, or
   `POST /v1/schedule`).
2. `RateLimitMiddleware` checks the per-key/per-IP fixed-window budget first
   (`api/rate_limit.py`); over budget returns 429 before anything else runs.
3. `ObservabilityMiddleware` assigns/propagates a request id, times the
   request, and records Prometheus counters/histograms (`api/metrics.py`).
4. The `v1_router`'s `require_api_key` dependency (`api/security.py`) checks
   `X-API-Key` against `API_KEYS` — a no-op when that setting is unset.
5. The route handler (`api/routes.py`) calls into `ForecastService`
   (`api/service.py`), which holds the already-loaded, already-validated
   model artifacts and precomputed forecast frames from startup — no
   per-request disk I/O or retraining.
6. For `/explain`, `ForecastService.explain` reuses the same loaded
   `ForecastModel` and its historical `series` to call
   `models/explain.py`'s `explain_forecast`, which ranks LightGBM's native
   TreeSHAP contributions.
7. Response schemas (`api/schemas.py`) validate and serialize the result;
   `ServiceUnavailableError`/generic exception handlers in `api/main.py`
   sanitize any failure before it reaches the client.

## Why this shape

- **No per-request model loading or training**: `ForecastService.__init__`
  does all of that once at startup, so request latency is just feature
  lookup + prediction, verified by the health check.
- **Middleware order matters**: rate limiting runs before auth so an
  unauthenticated flood is still bounded, and before the route handler so a
  limited request never reaches business logic.
- **Fail-safe monitoring**: a webhook failure is logged and reported, never
  raised — the CLI's exit code (2 for `alert`) is the one contract downstream
  automation (`.github/workflows/refresh.yml`) actually depends on.
- **Dashboard/API separation**: the Streamlit app only ever speaks HTTP to
  the API (`CARBON_API_URL`), so they can be deployed to two different free
  hosts independently (see the [deployment guide](deployment.md)).
