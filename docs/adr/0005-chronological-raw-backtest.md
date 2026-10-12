# ADR 0005: Chronological evaluation on raw observations

## Context

Decision D5 requires a rolling-origin evaluation. Interim cleaning uses
centered spike windows and interpolation (ADR 0011), so truncating an already
cleaned full-history series cannot undo its future-information leakage.

## Decision

Default evaluation to the raw snapshot. Demand <= 0 is masked pointwise;
carbon intensity is recomputed pointwise from raw fuel generation and the
documented factor configuration. Preserve gaps without interpolation or
centered filtering. Capture input/factor SHA-256 digests in reports.

Backtest the last six calendar months, issuing once daily at local midnight.
Refit from all history through the issue every 30 local calendar days.
Physically copy/truncate series passed to fit and predict at their respective
cutoffs. Attach realized labels afterwards; labels beyond test_end are NaN.
For alternative configured issue hours, skip ambiguous/nonexistent local times.
Reject malformed forecast timestamps, horizons, infinite values and crossing.

Report point and interval observation counts separately. Compare models on
the same finite-label, finite-prediction pairs for gate G3, since a missing
weekly anchor can prevent a baseline prediction where LightGBM still predicts.
Unpaired full-model summaries remain available for transparency.

Processed-data evaluation requires explicit `--data-source processed` and is
labelled exploratory retrospective data; it cannot establish leakage-safe G3.

## Consequences

Raw anomalies remain visible in evaluation rather than being removed using
future observations. This is an issue-time computation simulation on latest
revisions, with zero reporting latency assumed. EIA publication vintages and
original release delays are not reconstructed. It is not a strict historical
as-published replay. Carbon remains a partial observed-generation proxy.

Test-period results are published even if G3 fails. Test results must not be
used for selecting features or hyperparameters. Any investigation that changes
the model must select changes on a pre-test chronological validation period
and report the original test result too.
