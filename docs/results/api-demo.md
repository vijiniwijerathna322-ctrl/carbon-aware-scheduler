# Native offline API verification

Verified on 2026-10-12 with the tracked real CISO demo, no EIA key, and the frozen
lockfile. Health, six-hour forecasts for both targets, model listing and scheduling
returned HTTP 200. Artifact/snapshot SHA-256 digests were verified, and native
requests with the current carbon snapshot and demo mode disabled returned stale
503 as expected.

Carbon issue/data-as-of: `2026-10-11T06:00:00Z`. Demand issue/data-as-of:
`2026-10-12T05:00:00Z`. The demo does not advance these dates.

For a 2-hour, 7 kW median job with deadline `2026-10-12T06:00:00Z`, the recommendation
is `2026-10-11T18:00:00Z` through `20:00:00Z`: expected median 2,271.06 gCO2e versus
run-now 3,656.14 gCO2e, or 37.88% expected savings. This is a forecast estimate,
not a measured realized result. Summed lower/upper estimates are 1,815.26 / 2,601.13
gCO2e; they are not calibrated job-level confidence bounds. Carbon G4 remains a miss.

The Dockerfile, read-only/non-root smoke script, CI job and image base digest are
prepared. The official Python `3.11.17-slim-bookworm` manifest digest was verified
against Docker Registry on this date. Shell syntax checks pass. **Container build,
Linux startup, image size and Docker smoke have not been verified locally:** Docker
is not installed and WSL reports no installation. GitHub CI has not been triggered
from this local branch. Plan 07 and the MVP gate remain pending those checks; no
release tag has been created.

Local quality gate: 255 tests passed (1 live test excluded), 93.33% coverage; Ruff, formatting, mypy and offline lock consistency passed. The TestClient dependency emits a deprecation warning for its supported httpx compatibility path; tests remain passing.
