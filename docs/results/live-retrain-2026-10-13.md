# Live retraining validation: 2026-10-13

Repository-secret placement is resolved. Both regions successfully ingested EIA
history, built their datasets, fitted candidates and completed chronological
held-out CQR evaluations on GitHub runners.

## CISO

[Run 38349276638](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/38349276638)
passed evaluation and its required quality checks. Artifact upload and candidate
branch creation succeeded. The final draft-PR step failed because GitHub Actions
was not permitted to create or approve pull requests. The run remains failed.
The connected GitHub account created [draft PR 6](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/pull/6)
from the retained candidate branch without rerunning training.

The paired comparison uses 8,702 finite demand rows and 8,662 finite carbon rows.
Six revised demand labels were excluded; 48 forecast keys on each side did not
overlap. These figures describe the matched cohort, not the whole new backtest.

| Paired metric | Previous | Candidate |
|---|---:|---:|
| Demand coverage | 77.33% | 77.38% |
| Demand MAE (MWh) | 1254.4073 | 1251.5751 |
| Carbon coverage | 71.77% | 71.68% |
| Carbon MAE (gCO2e/kWh) | 33.3409 | 33.7151 |

Recommendation: retain the draft for review, without promoting this candidate.
Carbon coverage remains below nominal 80% and both carbon coverage and MAE
regress on the matched cohort. Small demand improvements do not resolve that
failure. These are rolling-origin pipeline evaluations, not held-out validation
of the final artifact fitted through the end of history. Existing deployed
selections remain in place.

## ERCO

[Run 38349279499](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/38349279499)
completed ingestion, fitting, held-out evaluation and its quality gate. The final
PR step failed with the same Actions permission denial. The connected account
opened [draft PR 7](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/pull/7)
from the retained candidate branch.
There is no previously approved ERCO deployment bundle to compare against.

| ERCO held-out metric | Measured value |
|---|---:|
| Demand coverage (8,758 finite rows) | 74.72% |
| Demand MAE (MWh) | 2529.7684 |
| Carbon coverage (8,710 finite rows) | 79.48% |
| Carbon MAE (gCO2e/kWh) | 34.2151 |

Demand coverage at 25–48 hours is 73.99%; carbon coverage by bucket is
81.23%, 79.73% and 78.86%. Review the demand coverage gate before any promotion.
Previous-missing diagnostics compare candidate rows to themselves solely to
validate finite support; they are not evidence of a previous ERCO model.

## Remaining acceptance

Review the ERCO results, execute its scheduling replay and monitoring, and
validate live refresh with approved region bundles. Future automatic PR creation
requires the repository's Actions PR setting to be enabled; the observed runner
denial takes precedence over earlier setup confirmation. No release tag or new
model promotion is implied by this execution record.
