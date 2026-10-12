# ADR 0015: Startup snapshots and offline container (D8)

## Context

The MVP needs forecast and scheduling endpoints without an EIA key. Models were
trained on raw targets, so serving processed/interpolated history would change
the feature distribution. Missing artifacts must remain observable. The original
plan's processed-data copy contract therefore needs to follow the raw policy.

## Decision

Use a FastAPI lifespan to create one service, validate both current artifacts and
their raw data snapshot, and precompute forecasts once. Each request receives a
deep copy. Models, data and forecasts are not changed while the service runs;
restart after refreshing them. Issue time and freshness are target-specific last
finite observations. More than six hours old is HTTP 503 with `data_stale`, except
in explicit demo mode. The health endpoint also checks freshness of both targets.

Expose the four planned endpoints with timezone-aware UTC responses. Schedule
requests use carbon, clamp past arrivals to the first forecast hour, and report
the adjustment. Reject deadlines beyond the available 48 forecast slots. Keep
errors categorical and omit server paths or tracebacks. Model listing exposes
only public version/training fields.

Generate demo assets into a new staged directory, copy only current artifacts,
retain 400 days of raw history, record hashes and verify serving before publishing
the directory. Commit the small explicit demo without credentials. Use a pinned
official slim Python image, frozen dependency lock and a separate runtime stage
with libgomp, a non-root user, a health check and no runtime writes outside /tmp.
The smoke test runs the real image read-only and derives schedule dates from its
frozen issue time. Add that test to CI.

## Consequences

Serving is reproducible and independent of request concurrency or network access.
It does not refresh automatically yet. Demo freshness bypass is visible in notes,
and carbon interval limitations remain explicit. Target issue times can differ:
latest carbon fuel data may lag demand. Container verification requires Docker;
without a runtime, native API checks do not establish Linux image compatibility.

Implementation references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/),
[official Python image](https://hub.docker.com/_/python).
