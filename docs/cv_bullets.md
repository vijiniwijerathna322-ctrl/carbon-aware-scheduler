# Portfolio wording and interview preparation

- Built leakage-aware 48-hour grid forecasts using chronological raw-data evaluation and conformal calibration; disclosed held-out demand coverage of 77.35% and carbon coverage of 71.57% against nominal 80%.
- Replayed 2,726 flexible-load scenarios per strategy; median scheduling achieved 29.37% mean proxy savings versus immediate execution, compared with a 33.17% hindsight oracle.
- Implemented a credential-free Docker/FastAPI demo, tested model registry, drift/coverage monitoring and review-based automation; a sampled 30% intensity shift produced a coverage alarm at day 7.

Numbers trace to [CQR](results/backtest-cqr.md), [scheduling](results/schedule-backtest.md) and [shift simulation](results/drift-simulation.md). Do not claim production deployment, ERCO performance, validated carbon 80% intervals or measured real-world avoided emissions.

## A 60-second explanation

I built a carbon-aware scheduler to connect probabilistic forecasting with decisions. It takes hourly EIA grid data, constructs a clearly scoped generation-based carbon proxy and forecasts the next 48 hours. I used chronological evaluation and physically truncated features to avoid future leakage. Conformal calibration helped quantify uncertainty, but carbon coverage missed its target, so I kept that failure visible. Scheduling replay showed roughly 29% mean proxy savings for illustrative median-based jobs, with the hindsight oracle providing a meaningful upper comparison. I packaged a frozen demo in a non-root, read-only Docker service and added drift and realized-coverage monitoring. The most important result is not just a model score: it is an auditable path from data quality to forecasts, decisions and honest operational limits.

## Why conformal?

Quantile regressors alone do not establish the desired realized coverage. A held-aside calibration window supplies a correction without changing the median forecast. Exchangeability assumptions are strained by hourly dependence and changing conditions. That is why I report held-out bucket/hour coverage and retain the carbon failure rather than presenting nominal coverage as a guarantee.

## How was leakage prevented?

Forecast inputs are physically truncated at the issue time, and lag/rolling features use only that prefix. Targets do not extend past each fit/calibration boundary. Rolling-origin test predictions are made before their realized labels are attached. Raw pointwise data avoids retrospective cleaning, although latest revisions and zero latency remain documented limitations.

## Why a generation-based proxy?

EIA provides an observable hourly fuel mix, allowing a reproducible technology-weighted proxy. It is useful for illustrating decision replay when marginal emissions are unavailable. Imports, heterogeneous fuels and storage accounting limit the scope. I would not interpret average-mix reductions as verified avoided emissions.

## What happens under drift?

Input PSI/KS, realized interval coverage and error ratios measure different problems. Monitoring excludes pre-fit issues, counts missing actuals and marks unavailable performance as insufficient data. Alerts preserve diagnostics and require review, without automatically retraining deployed models. The shift experiment demonstrated a sampled coverage alarm by day 7, not a universal detection guarantee.

## What would change with more time?

I would collect publication-vintage observations and forecast weather vintages before stronger live claims. I would test recalibration strategies on a new chronological validation cohort, not retune the published test period. ERCO is a planned generalisation check but remains unmeasured. Fleet-specific workloads and marginal-emissions data would be needed to estimate practical avoided emissions.
