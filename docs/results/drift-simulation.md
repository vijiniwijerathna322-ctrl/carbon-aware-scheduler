# Drift simulation: CISO intensity +30%

Isolated weather-free default 400-tree CQR models fit through `2026-09-14T05:00:00+00:00`; the shift begins `2026-10-05T06:00:00+00:00`. Production pointers and raw files were not changed. The loader overlays intensity only in memory after fitting; both artifact versions, source hashes and overlay hash are in the JSON diagnostics.

| Checkpoint | Realized hours | Coverage | Coverage status | MAE ratio | Target PSI | Overall |
|---|---|---|---|---|---|---|
| before | 336 | 82.14% | ok | 0.82 | 2.426 | alert |
| day_1 | 336 | 78.27% | ok | 0.92 | 2.499 | alert |
| day_3 | 336 | 76.79% | ok | 1.00 | 2.736 | alert |
| day_7 | 313 | 67.09% | alert | 1.07 | 3.628 | alert |

First sampled post-shift coverage alert: day_7. Input PSI/KS and coverage measure different changes. Overall alerts can precede coverage alarms due to seasonality or input drift; serial dependence and overlapping reference windows make p-values operational heuristics. MAE baselines use earlier held-out CQR rows, never calibration scores. Checkpoints are sampled at days 1, 3 and 7, so delay is a bound, not an hourly estimate.

A separate real tiny-model test on a stationary repeating weekly synthetic region verifies healthy pre-shift coverage and a coverage alert after seven days; this does not establish a seven-day guarantee on real deployments.
