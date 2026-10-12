# ADR 0004: Chronological horizon-bucket CQR

## Context

Decision D4 needs calibrated nominal 80% intervals. The raw quantile model's
held-out coverage is below nominal, and errors vary with forecast horizon.
ADR 0002 already documents the global quantile model; this ADR documents D4.

## Decision

Reserve the final 90 days before each fit_end for calibration. Training labels
must have target_time <= calibration_start. Calibration issues must be strictly
later than calibration_start and their labels at or before fit_end. Both windows
use the pointwise raw-target policy from ADR 0005. No future labels enter fit or
prediction features. Require at least 30 calendar days of pre-calibration history.

For each finite calibration row compute max(q10 - y, y - q90). Use the kth order
statistic, k = min(n, ceil((n+1)*0.8)), within buckets 1–6, 7–24, 25–48. This is
the empirical inverse-CDF quantile at k/n, without interpolation. A generic
"higher" quantile over zero-based positions produces a different rank and is
not used. Fewer than 30 bucket rows fall back to the pooled correction with a
warning. No finite pooled rows cause a clear error. Constant labels use their
actual scores; a zero correction is allowed when the observed scores warrant it.

Adjust to [q10 - correction, q90 + correction]. Negative corrections shrink
intervals. Collapse a crossed interval to its midpoint, then widen minimally to
include the unchanged median. This preserves the forecast schema's ordering and
cannot reduce coverage relative to the collapsed interval.

## Consequences

CQR supplies an exchangeability-based marginal guarantee, not unconditional
coverage under serial dependence or distribution shift. Horizon bucket fallback
mixes error scales and is disclosed. Reused calibration scores are descriptive,
not a held-out evaluation; G4 uses only the six test months. No test-period tuning
is allowed. Coverage failures are retained and documented.

Only alpha=0.2 is supported by the fixed q10/q50/q90 model contract. Other alpha
values raise explicitly. Different interval levels require a new base-quantile
schema rather than relabelling the existing model.
