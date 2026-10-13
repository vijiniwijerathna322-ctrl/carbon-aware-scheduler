# ERCO scheduling replay

Test interval: 2026-04-13T05:00:00+00:00 through 2026-10-13T05:00:00+00:00 (inclusive UTC).

Illustrative constant-power 7 kW EV jobs: durations 1, 2, 4, 8 hours; deadline windows 6, 12, 24, 36 hours. Arrival is the daily forecast issue time. These overlapping scenarios are equally weighted, not a measured fleet workload.

The issue-hour observation supplies h=0 under zero observation latency; h=1 onward uses CQR forecasts only. Actual future values only score outcomes and the hindsight oracle. Complete actual coverage of every feasible hour is required, preventing oracle comparisons on unequal support.

Savings are percentages: 100 × (baseline − chosen) / baseline. Zero baselines use zero by convention. Negative lower bounds are clipped to physical zero. Upper is an uncertainty heuristic: review this region's carbon coverage gate; summed pointwise bounds are not a calibrated job-level confidence interval.

## Strategy comparison

| bucket | n | mean_savings_pct | mean_oracle_savings_pct | share_better_than_baseline | mean_regret_gco2 |
|---|---|---|---|---|---|
| median | 2726 | 20.872840 | 22.880929 | 0.895451 | 120.653208 |
| upper | 2726 | 17.947653 | 22.880929 | 0.681218 | 282.516199 |

## median

Scored 2726 / 2760 jobs.

| bucket | n | mean_savings_pct | mean_oracle_savings_pct | share_better_than_baseline | mean_regret_gco2 |
|---|---|---|---|---|---|
| 6.0 | 546 | 1.605981 | 3.611946 | 0.587912 | 100.428612 |
| 12.0 | 728 | 20.292621 | 20.934410 | 0.947802 | 46.895858 |
| 24.0 | 728 | 28.443749 | 30.298143 | 0.989011 | 114.363134 |
| 36.0 | 724 | 28.373508 | 31.911592 | 0.980663 | 216.395132 |
| all | 2726 | 20.872840 | 22.880929 | 0.895451 | 120.653208 |

Skipped reasons: {"incomplete actual window": 34}

## upper

Scored 2726 / 2760 jobs.

| bucket | n | mean_savings_pct | mean_oracle_savings_pct | share_better_than_baseline | mean_regret_gco2 |
|---|---|---|---|---|---|
| 6.0 | 546 | 0.247350 | 3.611946 | 0.071429 | 146.843253 |
| 12.0 | 728 | 16.451885 | 20.934410 | 0.732143 | 315.605240 |
| 24.0 | 728 | 25.347946 | 30.298143 | 0.884615 | 273.497441 |
| 36.0 | 724 | 25.359076 | 31.911592 | 0.885359 | 360.629820 |
| all | 2726 | 17.947653 | 22.880929 | 0.681218 | 282.516199 |

Skipped reasons: {"incomplete actual window": 34}

G5: PASS (median mean realized savings > 0).

## Provenance

```json
{
  "carbon_scope": "Observed covered generation mix; partial fuel observations and excluded OTH; imports ignored.",
  "data_source": "raw",
  "factors_sha256": "5697a2fcd173474d398380d385cd6885099815473909971d1a75c99fee8b1d64",
  "forecast_metadata": {
    "calibration_days": 90,
    "carbon_scope": "Observed covered generation mix; partial fuel observations and excluded OTH; imports ignored.",
    "data_source": "raw",
    "factors_sha256": "5697a2fcd173474d398380d385cd6885099815473909971d1a75c99fee8b1d64",
    "input_sha256": "5c940bc300699ef96f42853e6fd30df5b06a5b709a5fb0e1eb821a8382397b28",
    "limitations": "Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.",
    "model_parameters": "{\"colsample_bytree\": 0.8, \"issue_step_h\": 3, \"learning_rate\": 0.05, \"min_child_samples\": 50, \"n_estimators\": 400, \"n_jobs\": 1, \"num_leaves\": 31, \"seed\": 42, \"subsample\": 0.8, \"subsample_freq\": 1, \"verbose\": -1}",
    "preprocessing": "Pointwise raw observations; no interpolation or centered spike filtering.",
    "test_end": "2026-10-13T05:00:00+00:00",
    "test_start": "2026-04-13T05:00:00+00:00",
    "timezone": "America/Chicago"
  },
  "forecast_sha256": "730ba67b3da8bb509dc0ce2649d7429db0b9fb6b8525f0cf151d6a652bc317ef",
  "input_sha256": "5c940bc300699ef96f42853e6fd30df5b06a5b709a5fb0e1eb821a8382397b28",
  "limitations": "Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.",
  "preprocessing": "Pointwise raw observations; no interpolation or centered spike filtering."
}
```
