# ADR 0002: Global quantile LightGBM models

## Context

Decision D2 needs 48-hour forecasts without maintaining 48 independent models.
The model must support missing lag/anchor observations and reproducible fits.

## Decision

For each target, fit three global LightGBM regressors with quantile objectives
at 0.1, 0.5 and 0.9. Horizon is an input feature. Use the plan's 400-tree default,
seed 42, one CPU thread, deterministic mode and column-wise histogram building.
Defaults are recorded with results. The wrapper accepts parameter overrides for
training-budget tests; objective, quantile alpha, seed and thread settings remain
fixed by the implementation. Only the fixed three quantile levels are supported
by the current q10/q50/q90 schema.

Sort each prediction row to repair crossing before exposing bounds and median.
Keep missing features as NaN. Reject infinite features and nonfinite training
targets. The forecaster constructs training issues every three UTC hours,
truncates observations at fit_end and drops rows with missing labels or targets
after fit_end. Prediction truncates history at issue_time.

## Consequences

Three models share statistical strength across horizons. They produce raw
quantile intervals, which are not yet calibrated; Plan 05 adds calibration.
Sorting may alter the returned median where quantiles cross. Determinism is
tested for identical seeds and environments, not promised across library or
hardware versions. Libraries are pinned in uv.lock.

Parameters follow the official [LGBMRegressor API](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMRegressor.html)
and [determinism documentation](https://lightgbm.readthedocs.io/en/stable/Parameters.html#deterministic).
