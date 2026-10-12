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

Local quality gate: 255 tests passed (1 live test excluded), 93.37% coverage; Ruff, formatting, mypy and offline lock consistency passed. The TestClient dependency emits a deprecation warning for its supported httpx compatibility path; tests remain passing.

- Windows demo staging now inherits workspace permissions, and Git preserves exact demo bytes across platforms for manifest verification.

Next verification step: publish branch `plan/07-api-and-docker` to `vijiniwijerathna322-ctrl/carbon-aware-scheduler` and inspect both CI jobs. Automatic approval review rejected the attempted push for missing explicit destination/payload authorization; the repository was not uploaded. The branch includes earlier unpushed project commits plus approximately 4.9 MB of demo observations and model artifacts. Current `.env` and full ignored data/models directories are not tracked. Docker verification remains pending.

## Verified GitHub CI

The user authorized the upload and branch `plan/07-api-and-docker` was pushed. [CI run 38251457125](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/38251457125) passed both Linux quality checks and the offline/non-root/read-only Docker smoke at commit `f23659b`. Image size: 587,311,058 bytes (587.31 MB), below the 600 MB target. Initial failures exposed platform-specific NumPy resolution and factor-file newline conversion; NumPy is now pinned to 2.4.6 and factor bytes are preserved. Local Docker is still unavailable, but the actual image was verified on the clean CI runner. Earlier permission/pending notes above describe the previous state. Main merge and release tag remain pending.
