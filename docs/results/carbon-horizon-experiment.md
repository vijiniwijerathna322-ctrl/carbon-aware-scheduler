# CISO carbon calibration-partition experiment

This experiment compares the current three horizon buckets with 48 individual
horizon corrections, using the same quantile model settings, 90-day calibration
window, seed 42 and training cutoff. Both variants use daily local-midnight
issues during March 2025; raw inputs are physically truncated at March 31,
2025 07:00 UTC. Model defaults and deployed registry pointers are unchanged.

The script rejects differences in forecast keys, labels or point medians, so
the comparison isolates correction partitioning rather than base-model changes.
Per-horizon calibration retains the existing finite-sample correction and
minimum-point fallback behaviour. Neither variant tunes parameters on the
already inspected 2026 held-out or post-fit monitored outcomes.

## Protocol and verification

- Successful run: 39277616486, workflow `carbon-horizon-experiment.yml`.
- Script: `scripts/experiment_carbon_horizons.py`.
- Tests verify future-history exclusion and rejection of changed point models.
- Full local suite: 322 passed, 1 deselected, 93.08% coverage.
- Ruff, formatting, mypy and actionlint passed.
- Linux/Docker CI run 39277616179 passed.

## Measured result

| Variant | Coverage | Mean width | MAE | Winkler | G4 |
|---|---:|---:|---:|---:|---|
| Three buckets | 72.67% | 83.1838 | 31.6154 | 146.0454 | fail |
| Per horizon | 72.25% | 83.4743 | 31.6154 | 146.0254 | fail |

Widths, MAE and Winkler are in carbon-proxy gCO2e/kWh units. Both variants score
1,416 identical finite forecast rows. Short-horizon coverage falls from 72.22%
to 70.00%; 7-24-hour coverage falls from 77.41% to 77.04%; 25-48-hour coverage
is unchanged at 69.11%. The tiny aggregate Winkler reduction does not establish
a meaningful improvement; no significance claim is made.

Decision: reject this partition change for promotion. It slightly widens average
intervals while reducing coverage, and both variants miss the fixed G4 gate.
Keep the existing defaults and the documented research-only deployment scope.
This negative result narrows the investigation without claiming to resolve the
observed current under-coverage.

[Comparison JSON](carbon-horizon-experiment/comparison.json) and both prediction
Parquets are committed. The artifact ZIP digest was verified before extraction;
the successful runner also enforced identical keys, labels and medians.

## Interpretation boundary

March 2025 is an exploratory historical cohort, not confirmatory evidence that a
replacement would pass current production coverage. Dependent hourly outcomes,
latest-revision snapshots, zero observation latency and the small seasonal scope
remain limitations. A result must be evaluated on coverage, interval width and
Winkler score together; merely widening intervals is not a sufficient decision.
Any subsequent candidate needs a frozen protocol and separate evaluation before
promotion. The research release remains unchanged.
