# CISO held-out CQR interval backtest

Daily local-midnight issues, horizons 1–48, refits every 30 local calendar days. Each fit reserves its final 90 days for calibration and trains only on targets at or before calibration_start. Calibration issues are strictly later than that boundary; calibration targets never exceed fit_end. Only realized labels in the six test months contribute to tables below.

Nominal coverage is 80%. G4 requires overall coverage within 77–83% and at least 70% in every horizon bucket. Defaults were fixed before seeing these test results. No test-period feature, parameter or calibration window tuning was performed. Reused training-time calibration summaries are excluded from held-out coverage claims.

Inputs follow ADR 0005: pointwise raw demand and carbon proxy, without retrospective cleaning. Latest revisions and zero observation latency are assumed. Partial fuel mixes, excluded OTH/storage and ignored imports remain limitations. CQR's exchangeability assumption does not remove time-series dependence or distribution drift (ADR 0004).

# Rolling-origin backtest: CISO / demand_mwh

## cqr

Test interval (UTC): 2026-04-12T05:00:00+00:00 to 2026-10-12T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. CQR intervals use a separate earlier calibration window.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1098 | 1098 | 421.167551 | 0.863388 | 1622.397631 | 89.375706 | 111.279381 | 2006.550866 |
| 7-24 | 3292 | 3292 | 1218.007322 | 0.750608 | 3667.057950 | 260.404070 | 326.360190 | 5867.642596 |
| 25-48 | 4366 | 4366 | 1489.956425 | 0.768209 | 4323.871788 | 311.203711 | 406.322584 | 7175.262948 |
| all | 8756 | 8756 | 1253.685681 | 0.773527 | 3738.164870 | 264.287360 | 339.260725 | 6035.480849 |

G4: PASS (overall 77–83%; each horizon bucket ≥70%).

### Coverage by horizon_bucket

| bucket | n | coverage | mean_width |
|---|---|---|---|
| 1-6 | 1098 | 0.863388 | 1622.397631 |
| 7-24 | 3292 | 0.750608 | 3667.057950 |
| 25-48 | 4366 | 0.768209 | 4323.871788 |
| all | 8756 | 0.773527 | 3738.164870 |

### Coverage by hour_local

| bucket | n | coverage | mean_width |
|---|---|---|---|
| 0 | 363 | 0.826446 | 3004.073782 |
| 1 | 365 | 0.898630 | 2421.329890 |
| 2 | 365 | 0.887671 | 2153.734050 |
| 3 | 365 | 0.846575 | 2007.446068 |
| 4 | 365 | 0.827397 | 1931.125944 |
| 5 | 365 | 0.849315 | 1847.849579 |
| 6 | 365 | 0.835616 | 1899.009263 |
| 7 | 365 | 0.843836 | 2159.425708 |
| 8 | 365 | 0.717808 | 2652.412593 |
| 9 | 365 | 0.638356 | 3342.353147 |
| 10 | 365 | 0.594521 | 3831.835979 |
| 11 | 365 | 0.652055 | 4196.074730 |
| 12 | 365 | 0.673973 | 4458.977969 |
| 13 | 365 | 0.753425 | 4671.791278 |
| 14 | 365 | 0.739726 | 4862.608395 |
| 15 | 365 | 0.712329 | 5174.599287 |
| 16 | 365 | 0.745205 | 5637.392740 |
| 17 | 365 | 0.726027 | 5744.753370 |
| 18 | 365 | 0.728767 | 5453.075004 |
| 19 | 365 | 0.758904 | 5225.879327 |
| 20 | 365 | 0.808219 | 4987.896403 |
| 21 | 365 | 0.835616 | 4535.704536 |
| 22 | 365 | 0.832877 | 4001.327180 |
| 23 | 363 | 0.831956 | 3510.008058 |

### Coverage by month_local

| bucket | n | coverage | mean_width |
|---|---|---|---|
| 1 | 0 | N/A | N/A |
| 2 | 0 | N/A | N/A |
| 3 | 0 | N/A | N/A |
| 4 | 886 | 0.839729 | 2693.053341 |
| 5 | 1488 | 0.827285 | 3314.173965 |
| 6 | 1440 | 0.786806 | 3547.749721 |
| 7 | 1488 | 0.739247 | 3430.194148 |
| 8 | 1488 | 0.721774 | 3880.624500 |
| 9 | 1440 | 0.808333 | 4635.138721 |
| 10 | 526 | 0.621673 | 5231.897288 |
| 11 | 0 | N/A | N/A |
| 12 | 0 | N/A | N/A |

- calibration_days: 90
- data_source: raw
- input_sha256: 1c09b875ae857d5962070f40c23dc00910f3e5d6095a550d2fb13a41805e3bd7
- limitations: Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.
- model_parameters: {"colsample_bytree": 0.8, "issue_step_h": 3, "learning_rate": 0.05, "min_child_samples": 50, "n_estimators": 400, "n_jobs": 1, "num_leaves": 31, "seed": 42, "subsample": 0.8, "subsample_freq": 1, "verbose": -1}
- preprocessing: Pointwise raw observations; no interpolation or centered spike filtering.
- timezone: America/Los_Angeles


## Paired CQR median versus weekly baseline: demand_mwh

| bucket | n | mae_naive | mae_lgbm | improvement_percent | g3_pass |
|---|---|---|---|---|---|
| 1-6 | 1098 | 1520.931694 | 421.167551 | 72.308582 | PASS |
| 7-24 | 3292 | 3074.166160 | 1218.007322 | 60.379262 | PASS |
| 25-48 | 4366 | 2695.065048 | 1489.956425 | 44.715382 | PASS |
| all | 8756 | 2690.359982 | 1253.685681 | 53.400820 | PASS |

- backtest_CISO_demand_mwh_cqr.parquet SHA-256: bd7ae45da92229a6a560952b58eeaa83ece9cbca95e91b729a469d2f62f09ddd
# Rolling-origin backtest: CISO / carbon_intensity_g_per_kwh

## cqr

Test interval (UTC): 2026-04-12T05:00:00+00:00 to 2026-10-12T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. CQR intervals use a separate earlier calibration window.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1092 | 1092 | 24.683115 | 0.777473 | 81.498749 | 6.001850 | 5.872683 | 118.745334 |
| 7-24 | 3275 | 3275 | 30.143745 | 0.696794 | 89.233088 | 5.668450 | 6.959954 | 126.284041 |
| 25-48 | 4343 | 4343 | 38.071846 | 0.714483 | 115.328488 | 7.144956 | 8.893802 | 160.387585 |
| all | 8710 | 8710 | 33.412256 | 0.715729 | 101.275157 | 6.446468 | 7.787899 | 142.343676 |

G4: FAIL (overall 77–83%; each horizon bucket ≥70%).

### Coverage by horizon_bucket

| bucket | n | coverage | mean_width |
|---|---|---|---|
| 1-6 | 1092 | 0.777473 | 81.498749 |
| 7-24 | 3275 | 0.696794 | 89.233088 |
| 25-48 | 4343 | 0.714483 | 115.328488 |
| all | 8710 | 0.715729 | 101.275157 |

### Coverage by hour_local

| bucket | n | coverage | mean_width |
|---|---|---|---|
| 0 | 361 | 0.750693 | 114.233310 |
| 1 | 363 | 0.787879 | 97.555863 |
| 2 | 363 | 0.774105 | 101.032077 |
| 3 | 363 | 0.754821 | 103.948838 |
| 4 | 363 | 0.741047 | 105.048207 |
| 5 | 363 | 0.746556 | 106.538228 |
| 6 | 363 | 0.763085 | 107.614658 |
| 7 | 363 | 0.790634 | 110.409552 |
| 8 | 363 | 0.754821 | 101.322947 |
| 9 | 363 | 0.677686 | 91.780205 |
| 10 | 363 | 0.683196 | 89.601199 |
| 11 | 363 | 0.666667 | 88.440410 |
| 12 | 363 | 0.663912 | 87.961988 |
| 13 | 363 | 0.661157 | 88.352735 |
| 14 | 363 | 0.647383 | 88.299186 |
| 15 | 363 | 0.647383 | 89.995126 |
| 16 | 363 | 0.628099 | 93.341646 |
| 17 | 363 | 0.661157 | 96.819081 |
| 18 | 363 | 0.666667 | 98.691127 |
| 19 | 363 | 0.752066 | 107.225036 |
| 20 | 363 | 0.749311 | 113.730496 |
| 21 | 363 | 0.738292 | 116.046547 |
| 22 | 363 | 0.738292 | 116.093745 |
| 23 | 363 | 0.732782 | 116.592962 |

### Coverage by month_local

| bucket | n | coverage | mean_width |
|---|---|---|---|
| 1 | 0 | N/A | N/A |
| 2 | 0 | N/A | N/A |
| 3 | 0 | N/A | N/A |
| 4 | 886 | 0.610609 | 103.563567 |
| 5 | 1488 | 0.600806 | 105.226137 |
| 6 | 1440 | 0.524306 | 100.712034 |
| 7 | 1488 | 0.913306 | 106.868579 |
| 8 | 1488 | 0.866263 | 91.192814 |
| 9 | 1440 | 0.661806 | 101.749500 |
| 10 | 480 | 0.922917 | 98.985094 |
| 11 | 0 | N/A | N/A |
| 12 | 0 | N/A | N/A |

- calibration_days: 90
- carbon_scope: Observed covered generation mix; partial fuel observations and excluded OTH; imports ignored.
- data_source: raw
- factors_sha256: 5697a2fcd173474d398380d385cd6885099815473909971d1a75c99fee8b1d64
- input_sha256: 1c09b875ae857d5962070f40c23dc00910f3e5d6095a550d2fb13a41805e3bd7
- limitations: Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.
- model_parameters: {"colsample_bytree": 0.8, "issue_step_h": 3, "learning_rate": 0.05, "min_child_samples": 50, "n_estimators": 400, "n_jobs": 1, "num_leaves": 31, "seed": 42, "subsample": 0.8, "subsample_freq": 1, "verbose": -1}
- preprocessing: Pointwise raw observations; no interpolation or centered spike filtering.
- timezone: America/Los_Angeles


## Paired CQR median versus weekly baseline: carbon_intensity_g_per_kwh

| bucket | n | mae_naive | mae_lgbm | improvement_percent | g3_pass |
|---|---|---|---|---|---|
| 1-6 | 1092 | 52.127399 | 24.683115 | 52.648481 | PASS |
| 7-24 | 3275 | 41.270433 | 30.143745 | 26.960435 | PASS |
| 25-48 | 4343 | 43.965357 | 38.071846 | 13.404898 | PASS |
| all | 8710 | 43.975354 | 33.412256 | 24.020495 | PASS |

- backtest_CISO_carbon_intensity_g_per_kwh_cqr.parquet SHA-256: c1e4da091b0b985d434536b76af37c1f117ee8c99f277ede5f80fb9c1755f083

## Combined G4: FAIL

The target is missed and is retained as a measured limitation. Coverage varies by local hour and month in the tables above. This fixed 90-day bucket calibration does not certify nominal held-out coverage under temporal drift. Future calibration changes must be selected on a pre-test chronological validation window and evaluated on fresh held-out data; these test results must remain visible.

## Reproducibility

- lightgbm: 4.7.0
- pandas: 3.0.6
- numpy: 2.4.6
- joblib: 1.6.0
- conformal.py SHA-256: ee1cb70c61a364702e88f9a28b2ac599b02a8b19a8f49a34b71dd08c037be635
- forecast_model.py SHA-256: a1c8bda76a2bf038576b8fa95100ee8004a880fa692090c20b4c223703254e18
