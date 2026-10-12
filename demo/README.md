# Frozen CISO demo

Generated with `carbon-scheduler make-demo --region CISO` on 2026-10-12.
Contains 400 days (9,600 hourly rows) of the pointwise raw EIA snapshot and the
current demand/carbon CQR artifacts. Assets total about 4.9 MB (decimal).
`manifest.json` records data dates, selected model versions and SHA-256 digests.
Only the two current model versions are copied; no API key is needed to serve.

Data source: [US Energy Information Administration, EIA-930](https://www.eia.gov/electricity/gridmonitor/).
The configured lifecycle factors and their references are in
`config/emission_factors.yaml`; intensity estimates reflect the observed covered
generation mix, exclude heterogeneous OTH/storage, and do not attribute imports.
Latest revisions and zero observation latency are assumed. Partial fuel
observations are retained; this is not complete whole-grid intensity.

Demand's last finite observation is 2026-10-12 05:00 UTC. Carbon's is
2026-10-11 06:00 UTC. `DEMO_MODE=1` bypasses the six-hour freshness gate but does
not advance issue times. Carbon's held-out interval coverage was 71.57% (G4 fail).
Intervals and sums of their endpoints are not validated nominal 80% job-level
bounds. Requests use dates relative to the frozen forecast issue.

The registry validates exact numerical dependency versions and Python major/minor.
The lockfile supplies matching package versions. The copied artifacts are trusted
local joblib files; do not replace them with untrusted serialized models.

To regenerate, use a new `--out-dir` directory; the command refuses to overwrite
an existing demo. Verify it before replacing these tracked assets.
