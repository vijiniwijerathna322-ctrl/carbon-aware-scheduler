# Model card

## Intended use

This portfolio system forecasts hourly balancing-authority demand and an observed-generation carbon proxy, then compares schedules for flexible illustrative loads. Intended users are developers and researchers studying forecasting, uncertainty and decision replay. It is not a grid-control system, marginal-emissions model, carbon-credit verification service or a guarantee of avoided emissions.

## Models and evaluation

Weather-free LightGBM quantile models predict 48 hourly horizons from issue-time lags, trailing statistics, calendar and horizon features. Separate demand and carbon artifacts reserve the final 90 days of each fit for conformal calibration. Global quantile models use the default 400-tree configuration, seed 42 and single-thread fitting. Training summaries reuse calibration data and are not held-out certification.

The measured CISO test period is 2026-04-12 05:00 through 2026-10-12 05:00 UTC, with daily local-midnight issues and chronological refits every 30 local days. All features are physically restricted to information available by issue time. The source is a latest-revision snapshot assuming zero publication latency, not an archived publication-vintage replay.

| Target / horizon | MAE | Realized coverage |
|---|---:|---:|
| Demand 1-6 | 421.17 MWh | 86.34% |
| Demand 7-24 | 1218.01 MWh | 75.06% |
| Demand 25-48 | 1489.96 MWh | 76.82% |
| Demand all | 1253.69 MWh | 77.35% |
| Carbon 1-6 | 24.68 gCO2e/kWh | 77.75% |
| Carbon 7-24 | 30.14 gCO2e/kWh | 69.68% |
| Carbon 25-48 | 38.07 gCO2e/kWh | 71.45% |
| Carbon all | 33.41 gCO2e/kWh | 71.57% |

Complete carbon bucket and local-hour tables are in [held-out CQR results](results/backtest-cqr.md). Nominal coverage is 80%. Demand passes the predeclared overall 77–83% and per-bucket 70% gate; carbon fails. The [coverage figure](figures/coverage.png) retains both targets and their hourly failure patterns. Do not describe carbon intervals as validated 80% bounds. Neither conformal calibration nor the monitoring tests remove serial dependence and distribution shift.

The shipped demand artifact uses raw history beginning 2021-01-01, fitting targets through 2026-07-14 05:00 UTC and calibrating strictly later targets through 2026-10-12 05:00 UTC. Carbon fitting ends 2026-07-13 06:00 UTC, with calibration through 2026-10-11 06:00 UTC. These final-artifact windows are separate from the earlier rolling refits used to produce the held-out tables.

## Decision results

[Scheduling replay](results/schedule-backtest.md) scores 2,726 equally weighted scenarios per strategy: mean median-strategy savings 29.37%, upper-strategy 27.35%, hindsight oracle 33.17%. These are proxy reductions relative to immediate execution, not measured fleet-wide avoided emissions. Nineteen incomplete windows per strategy were excluded. Summed upper endpoints are an uncertainty heuristic, not a calibrated job-level confidence interval.

## Failure modes and monitoring

Heat waves, holidays, outages, changing generation mix and wildfire disruptions are plausible distribution shifts; their individual effects have not been isolated here. Missing fuel categories, upstream revisions and stale observations can change the proxy. Carbon intervals already under-cover on this test cohort. The 30% intensity-shift experiment reaches 67.09% realized coverage at sampled day 7; pre-existing input alarms are disclosed. A seven-day detection guarantee is not claimed.

Monitoring scores only issues at or after artifact fit_end, selects the latest eligible forecast per realized hour, counts excluded values and uses at least 100 finite points for performance alerts. Newly trained models can legitimately have insufficient realized data. PSI/KS/binomial p-values are diagnostic heuristics under dependence, seasonality and multiple testing. Approved weather models require forecast-vintage logs before replay monitoring can be supported.

## Retraining, deployment and generalisation

Retraining creates draft candidates with paired held-out deltas and requires review before separate promotion. The offline Docker demo serves a frozen CISO snapshot without credentials. Live CISO refresh validated the alert path; drafts 6 and 7 retain real candidates, with no promotion. [ERCO results](results/second-region-erco.md) show demand/carbon MAE reductions of 40.69%/38.32% versus seasonal naive, coverage 74.72%/79.48%, and median/upper replay savings 20.87%/17.95%. Demand G4 fails while carbon passes. The earlier-period 180-day calibration experiment worsened coverage, so the 90-day default remains. Post-fit monitoring performance and GHCR acceptance remain pending. Archive-weather experiments are exploratory and were not promoted: realized weather does not establish live forecast performance.

## Ethical and physical scope

The proxy weights technology lifecycle factors by covered observed generation, excludes heterogeneous OTH/storage categories and ignores imports. It describes average generation mix rather than marginal response to a job. External environmental, economic and operational constraints are omitted. Reports should retain uncertainty, missing-data counts, failed gates and cohort provenance whenever results are shared.
