# CISO scheduling replay

Test interval: 2026-04-12T05:00:00+00:00 through 2026-10-12T05:00:00+00:00 (inclusive UTC).

Illustrative constant-power 7 kW EV jobs: durations 1, 2, 4, 8 hours; deadline windows 6, 12, 24, 36 hours. Arrival is the daily forecast issue time. These overlapping scenarios are equally weighted, not a measured fleet workload.

The issue-hour observation supplies h=0 under zero observation latency; h=1 onward uses CQR forecasts only. Actual future values only score outcomes and the hindsight oracle. Complete actual coverage of every feasible hour is required, preventing oracle comparisons on unequal support.

Savings are percentages: 100 × (baseline − chosen) / baseline. Zero baselines use zero by convention. Negative lower bounds are clipped to physical zero. Upper is an uncertainty heuristic: carbon G4 failed and summed pointwise bounds are not a calibrated job-level confidence interval.

## Strategy comparison

| bucket | n | mean_savings_pct | mean_oracle_savings_pct | share_better_than_baseline | mean_regret_gco2 |
|---|---|---|---|---|---|
| median | 2726 | 29.367233 | 33.174884 | 0.704329 | 82.945197 |
| upper | 2726 | 27.348151 | 33.174884 | 0.615187 | 111.674541 |

## median

Scored 2726 / 2745 jobs.

| bucket | n | mean_savings_pct | mean_oracle_savings_pct | share_better_than_baseline | mean_regret_gco2 |
|---|---|---|---|---|---|
| 6.0 | 546 | 0.735521 | 4.156726 | 0.184982 | 73.447719 |
| 12.0 | 728 | 31.780166 | 33.783747 | 0.825549 | 26.561063 |
| 24.0 | 728 | 38.515099 | 42.768212 | 0.837912 | 93.848514 |
| 36.0 | 724 | 39.334984 | 44.800186 | 0.839779 | 135.839753 |
| all | 2726 | 29.367233 | 33.174884 | 0.704329 | 82.945197 |

Skipped reasons: {"incomplete actual window": 19}

## upper

Scored 2726 / 2745 jobs.

| bucket | n | mean_savings_pct | mean_oracle_savings_pct | share_better_than_baseline | mean_regret_gco2 |
|---|---|---|---|---|---|
| 6.0 | 546 | 0.214606 | 4.156726 | 0.021978 | 81.577665 |
| 12.0 | 728 | 29.509101 | 33.783747 | 0.751374 | 54.091338 |
| 24.0 | 728 | 36.380203 | 42.768212 | 0.770604 | 120.783129 |
| 36.0 | 724 | 36.555899 | 44.800186 | 0.769337 | 183.114338 |
| all | 2726 | 27.348151 | 33.174884 | 0.615187 | 111.674541 |

Skipped reasons: {"incomplete actual window": 19}

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
    "input_sha256": "1c09b875ae857d5962070f40c23dc00910f3e5d6095a550d2fb13a41805e3bd7",
    "limitations": "Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.",
    "model_parameters": "{\"colsample_bytree\": 0.8, \"issue_step_h\": 3, \"learning_rate\": 0.05, \"min_child_samples\": 50, \"n_estimators\": 400, \"n_jobs\": 1, \"num_leaves\": 31, \"seed\": 42, \"subsample\": 0.8, \"subsample_freq\": 1, \"verbose\": -1}",
    "preprocessing": "Pointwise raw observations; no interpolation or centered spike filtering.",
    "test_end": "2026-10-12T05:00:00+00:00",
    "test_start": "2026-04-12T05:00:00+00:00",
    "timezone": "America/Los_Angeles"
  },
  "forecast_sha256": "c1e4da091b0b985d434536b76af37c1f117ee8c99f277ede5f80fb9c1755f083",
  "input_sha256": "1c09b875ae857d5962070f40c23dc00910f3e5d6095a550d2fb13a41805e3bd7",
  "limitations": "Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.",
  "preprocessing": "Pointwise raw observations; no interpolation or centered spike filtering."
}
```
