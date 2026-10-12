# CISO point-forecast backtest

Test data: 2026-04-12T05:00:00+00:00 through 2026-10-12T05:00:00+00:00 (UTC). Daily America/Los_Angeles midnight issues, horizons 1–48, 30-local-calendar-day refits. Each refit uses all earlier history. Training issues occur every three UTC hours. Defaults are unchanged from Plan 04; no tuning on this test period.

Raw observations are used pointwise without retrospective interpolation or centered cleaning. Demand <= 0 is masked; missing values are retained. This is a latest-revision simulation assuming zero reporting latency, not an as-published historical replay. Carbon describes the covered observed-generation lifecycle proxy, excluding OTH/storage and imports. Partial fuel data remains a limitation. See ADRs 0001, 0002, 0003 and 0005.

G3 compares paired finite predictions and identical labels. Full-model summaries below disclose differing availability. n_interval may differ from point n. Raw quantile coverage is uncalibrated, not a Plan 05 verdict.

## Paired comparison: demand_mwh

| bucket | n | mae_naive | mae_lgbm | improvement_percent | g3_pass |
|---|---|---|---|---|---|
| 1-6 | 1098 | 1520.931694 | 404.002414 | 73.437176 | PASS |
| 7-24 | 3292 | 3074.166160 | 1214.612451 | 60.489694 | PASS |
| 25-48 | 4366 | 2695.065048 | 1499.694963 | 44.354035 | PASS |
| all | 8756 | 2690.359982 | 1255.112728 | 53.347777 | PASS |

# Rolling-origin backtest: CISO / demand_mwh

## naive

Test interval (UTC): 2026-04-12T05:00:00+00:00 to 2026-10-12T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. Intervals are uncalibrated.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1098 | 0 | 1520.931694 | N/A | N/A | N/A | N/A | N/A |
| 7-24 | 3292 | 0 | 3074.166160 | N/A | N/A | N/A | N/A | N/A |
| 25-48 | 4366 | 0 | 2695.065048 | N/A | N/A | N/A | N/A | N/A |
| all | 8756 | 0 | 2690.359982 | N/A | N/A | N/A | N/A | N/A |



# Rolling-origin backtest: CISO / demand_mwh

## lgbm

Test interval (UTC): 2026-04-12T05:00:00+00:00 to 2026-10-12T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. Intervals are uncalibrated.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1098 | 1098 | 404.002414 | 0.799636 | 1376.350348 | 84.641219 | 110.729611 | 1953.708309 |
| 7-24 | 3292 | 3292 | 1214.612451 | 0.707473 | 3330.328737 | 258.055411 | 322.998876 | 5810.542862 |
| 25-48 | 4366 | 4366 | 1499.694963 | 0.732936 | 4017.363695 | 317.207954 | 405.256448 | 7224.644021 |
| all | 8756 | 8756 | 1255.112728 | 0.731727 | 3427.876288 | 265.804522 | 337.396421 | 6032.009436 |



### demand_mwh: hour_local

| bucket | n | mae_naive | mae_lgbm |
|---|---|---|---|
| 0 | 363 | 2114.258953 | 914.523367 |
| 1 | 365 | 1808.753425 | 609.817970 |
| 2 | 365 | 1635.441096 | 553.282144 |
| 3 | 365 | 1531.126027 | 548.545449 |
| 4 | 365 | 1520.967123 | 562.927857 |
| 5 | 365 | 1405.750685 | 503.101737 |
| 6 | 365 | 1244.295890 | 517.206367 |
| 7 | 365 | 1256.372603 | 599.996595 |
| 8 | 365 | 1743.646575 | 1028.431259 |
| 9 | 365 | 2681.068493 | 1526.679963 |
| 10 | 365 | 2888.230137 | 1610.718495 |
| 11 | 365 | 2953.947945 | 1578.189996 |
| 12 | 365 | 3038.920548 | 1607.860674 |
| 13 | 365 | 3099.682192 | 1577.979928 |
| 14 | 365 | 3371.005479 | 1673.278845 |
| 15 | 365 | 3704.567123 | 1860.195064 |
| 16 | 365 | 4060.517808 | 1946.127382 |
| 17 | 365 | 4243.780822 | 2053.305937 |
| 18 | 365 | 4154.526027 | 1896.061002 |
| 19 | 365 | 3988.873973 | 1766.627292 |
| 20 | 365 | 3626.969863 | 1567.260184 |
| 21 | 365 | 3196.643836 | 1354.414420 |
| 22 | 365 | 2845.224658 | 1212.549355 |
| 23 | 363 | 2449.592287 | 1050.637547 |

### demand_mwh: month_local

| bucket | n | mae_naive | mae_lgbm |
|---|---|---|---|
| 4 | 886 | 1295.616253 | 872.407533 |
| 5 | 1488 | 1596.098118 | 1009.627411 |
| 6 | 1440 | 2527.943056 | 1094.149326 |
| 7 | 1488 | 2099.887097 | 1237.671507 |
| 8 | 1488 | 2249.857527 | 1281.815311 |
| 9 | 1440 | 4946.540278 | 1502.589488 |
| 10 | 526 | 5319.783270 | 2331.156106 |

## Paired comparison: carbon_intensity_g_per_kwh

| bucket | n | mae_naive | mae_lgbm | improvement_percent | g3_pass |
|---|---|---|---|---|---|
| 1-6 | 1092 | 52.127399 | 23.355634 | 55.195090 | PASS |
| 7-24 | 3275 | 41.270433 | 22.115152 | 46.414054 | PASS |
| 25-48 | 4343 | 43.965357 | 31.698148 | 27.901988 | PASS |
| all | 8710 | 43.975354 | 27.048970 | 38.490613 | PASS |

# Rolling-origin backtest: CISO / carbon_intensity_g_per_kwh

## naive

Test interval (UTC): 2026-04-12T05:00:00+00:00 to 2026-10-12T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. Intervals are uncalibrated.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1092 | 0 | 52.127399 | N/A | N/A | N/A | N/A | N/A |
| 7-24 | 3275 | 0 | 41.270433 | N/A | N/A | N/A | N/A | N/A |
| 25-48 | 4343 | 0 | 43.965357 | N/A | N/A | N/A | N/A | N/A |
| all | 8710 | 0 | 43.975354 | N/A | N/A | N/A | N/A | N/A |



# Rolling-origin backtest: CISO / carbon_intensity_g_per_kwh

## lgbm

Test interval (UTC): 2026-04-12T05:00:00+00:00 to 2026-10-12T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. Intervals are uncalibrated.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1092 | 1092 | 23.355634 | 0.603480 | 54.417852 | 5.883496 | 5.382689 | 112.661853 |
| 7-24 | 3275 | 3275 | 22.115152 | 0.602137 | 50.591975 | 5.481347 | 4.737755 | 102.191012 |
| 25-48 | 4343 | 4343 | 31.698148 | 0.574027 | 69.551144 | 8.063613 | 7.181566 | 152.451793 |
| all | 8710 | 8710 | 27.048970 | 0.588289 | 60.525101 | 6.819341 | 6.037151 | 128.564919 |



### carbon_intensity_g_per_kwh: hour_local

| bucket | n | mae_naive | mae_lgbm |
|---|---|---|---|
| 0 | 361 | 54.985701 | 34.761799 |
| 1 | 363 | 52.983436 | 27.447396 |
| 2 | 363 | 53.471160 | 28.513252 |
| 3 | 363 | 52.985292 | 29.757823 |
| 4 | 363 | 52.261758 | 31.025946 |
| 5 | 363 | 50.825725 | 31.098739 |
| 6 | 363 | 49.398642 | 31.491773 |
| 7 | 363 | 44.498046 | 28.492144 |
| 8 | 363 | 36.808779 | 24.629324 |
| 9 | 363 | 33.663394 | 23.322224 |
| 10 | 363 | 30.489305 | 21.830060 |
| 11 | 363 | 29.858637 | 20.706729 |
| 12 | 363 | 30.655698 | 21.097517 |
| 13 | 363 | 31.251439 | 21.150533 |
| 14 | 363 | 32.760526 | 21.092084 |
| 15 | 363 | 34.427226 | 21.537298 |
| 16 | 363 | 36.272986 | 22.332802 |
| 17 | 363 | 37.978645 | 22.851513 |
| 18 | 363 | 40.220096 | 24.320372 |
| 19 | 363 | 46.812420 | 27.611024 |
| 20 | 363 | 55.641592 | 32.028295 |
| 21 | 363 | 56.209515 | 33.646286 |
| 22 | 363 | 55.575476 | 34.336112 |
| 23 | 363 | 55.433664 | 34.136740 |

### carbon_intensity_g_per_kwh: month_local

| bucket | n | mae_naive | mae_lgbm |
|---|---|---|---|
| 4 | 886 | 34.900823 | 27.141583 |
| 5 | 1488 | 31.612209 | 27.136833 |
| 6 | 1440 | 36.940861 | 29.098524 |
| 7 | 1488 | 50.628783 | 22.539427 |
| 8 | 1488 | 29.104630 | 21.142306 |
| 9 | 1440 | 68.107654 | 36.845626 |
| 10 | 480 | 73.231373 | 23.357264 |

## Gate G3: PASS

LightGBM must improve paired MAE in every horizon bucket for both targets. Individual monthly/hourly differences are diagnostics, not tuning criteria.

## Reproducibility

- Python: 3.11.17
- lightgbm: 4.7.0
- numpy: 2.4.6
- pandas: 3.0.6
- scikit-learn: 1.9.1
- LightGBM defaults: `{"colsample_bytree": 0.8, "issue_step_h": 3, "learning_rate": 0.05, "min_child_samples": 50, "n_estimators": 400, "n_jobs": 1, "num_leaves": 31, "seed": 42, "subsample": 0.8, "subsample_freq": 1, "verbose": -1}`
- raw input SHA-256: 1c09b875ae857d5962070f40c23dc00910f3e5d6095a550d2fb13a41805e3bd7
- emission factors SHA-256: 5697a2fcd173474d398380d385cd6885099815473909971d1a75c99fee8b1d64
- dependency lock SHA-256: b1ae7c137aabcc7b21fb598b18b246aa235d6c3e1605ac1b967cbeb43e25c897
- feature implementation SHA-256: 301718a4d7edf0852da62b8ffdab46fb1e52c92a790982051d2b240e4f0efce1
- model implementation SHA-256: 252dd42c4a108765bdaf54e41b64c851405fb81568033e7ad035fd695dbb3058
- backtest_CISO_carbon_intensity_g_per_kwh_lgbm.parquet SHA-256: 4f73607c4625d38ee858e329e9a02e4cd01b20eb820a1657bb21858685b39524
- backtest_CISO_carbon_intensity_g_per_kwh_naive.parquet SHA-256: 90e7eca3c6b5363934c404b12e6ea1e63413e2ea1f448ac7c85f576e755468d8
- backtest_CISO_demand_mwh_lgbm.parquet SHA-256: 0d068f77ffe50d1739a6ae3a7385bd2791405e26d0349c163520f2bd6bc980ec
- backtest_CISO_demand_mwh_naive.parquet SHA-256: b1e1394bb71cef7f6f4ed1b8de12c08d840ce5c3da44d5d1422091970b201b52
