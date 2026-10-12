# ADR 0014: Whole-hour scheduling and historical replay (D7)

## Context

Flexible jobs need a feasible start before a deadline, with a transparent run-now
comparison. CQR forecasts begin at horizon 1, while replay jobs arrive at the
forecast issue time. Carbon G4 missed its target; pointwise interval endpoints
also do not establish coverage for sums over jobs.

## Decision

Use UTC whole-hour starts, ceiling arrival and requiring each complete hour to
finish by the deadline. Minimize the rolling sum of either medians or upper
endpoints, choosing the earliest tied start. Constant power times summed hourly
intensity gives grams of CO2e. For interruptible jobs, choose the cheapest valid
hours and return their chronological list. The baseline always runs contiguously
from the ceiling of arrival.

Reject missing horizon coverage with the number of missing hours. Skip candidate
windows containing any missing endpoint. A missing baseline is an explicit error
because an expected savings comparison would be undefined. Clip negative lower
endpoints to physical zero; reject negative median/upper estimates. Report
savings in percent, using zero by convention when the baseline is zero.

Replay supplies the observed issue-hour intensity as a degenerate h=0 endpoint
under the existing zero observation latency assumption. Future actual values do
not influence recommendations. They score the chosen hours, baseline and
hindsight oracle. An incomplete actual window skips the entire scenario so the
oracle has the same complete feasible support. Preserve skipped rows and reasons.
Restrict actual scoring to the original held-out interval, verify raw-data and
factor hashes against the forecast sidecar, and compare strategies on identical
cohorts. A report with no scored scenarios fails explicitly.

## Consequences

These are retrospective scenario results on latest revisions, not a production
publication-vintage simulation or a causal estimate of avoided grid emissions.
The 7 kW EV job grid is illustrative and includes overlapping scenarios. Arrival
at local midnight is not representative of every workload. The oracle is a
hindsight bound within these scenarios. The upper strategy is a heuristic;
neither its pointwise carbon bounds nor job-level sums have validated nominal
80% coverage. A live API must define availability of the issue-hour measurement
or require arrivals inside its available forecast horizon.
