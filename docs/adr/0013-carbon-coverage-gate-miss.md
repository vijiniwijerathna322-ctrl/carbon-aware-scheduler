# ADR 0013: Retain the measured carbon coverage miss

## Context

The fixed 90-day horizon-bucket CQR evaluation uses held-out CISO observations
from 2026-04-12 05:00 through 2026-10-12 05:00 UTC. G4 requires overall 80%
coverage within 77–83%, and every horizon bucket at least 70%.

Demand passes: overall 77.35%, with 86.34%, 75.06%, 76.82% by horizon bucket.
Carbon fails: overall 71.57%, with 77.75%, 69.68%, 71.45% by horizon bucket.
Both CQR medians still beat the weekly baseline in every horizon bucket.

Carbon coverage varies markedly by local month: April 61.06%, May 60.08%,
June 52.43%, July 91.33%, August 86.63%, September 66.18%, October 92.29%.
Local 16:00 coverage is 62.81%, compared with 79.06% at 07:00. These are
descriptive diagnostics of uneven coverage, not proof of a particular causal
mechanism. Dependence, changing error distributions and partial fuel reporting
remain plausible limitations; no claim of exchangeable grid observations is made.

## Decision

Accept and document this gate miss under Plan 05's explicit "pass or documented"
Definition of Done. Keep the original fixed parameters, 90-day calibration
window and measured test results. Do not select a longer window or per-hour
correction using these already observed test outcomes.

Continue engineering the scheduler and API with explicit awareness that the
carbon interval has not met the nominal held-out target. An upper-bound strategy
is a heuristic using this model's estimated interval, not a validated 80%
carbon-emissions guarantee. Portfolio and model-card claims must retain the miss.

Future improvements must be selected on an earlier chronological validation
period and evaluated on fresh held-out observations, with these results retained.

## Consequences

Plan 05 is implemented and evaluated, while combined G4 remains FAIL. Interval
calibration infrastructure is functional; carbon coverage performance remains
an unresolved measured model limitation. Full metrics and provenance are in
`docs/results/backtest-cqr.md`. Reused calibration scores stored with artifacts
must never substitute for these held-out scores.
