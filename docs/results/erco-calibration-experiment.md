# ERCO demand calibration-window experiment

[Run 38356401563](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/38356401563)
completed a fixed-date exploratory comparison on March 2025, before the already
inspected April-October 2026 held-out period. Inputs were truncated at March 31,
2025 05:00 UTC before fitting/evaluation. Seed 42, issue step 3 hours, base
quantiles and nominal alpha 0.2 were unchanged. No model registry writes occur.

| Calibration window | Overall coverage | Mean width (MWh) | MAE (MWh) | G4 |
|---|---:|---:|---:|---|
| 90 days | 78.18% | 6712.92 | 2290.10 | pass |
| 180 days | 75.85% | 6578.06 | 2355.74 | fail |

Both variants scored 1,416 finite forecast rows. The 7-24-hour bucket coverage
fell from 75.19% to 70.74%; 25-48 hours fell from 80.75% to 79.02%. Longer
calibration narrowed the average interval and worsened MAE and Winkler score.
This comparison provides no support for replacing the 90-day default with 180
days. Keep the default and retain the documented 2026 demand G4 miss.

This is a pipeline comparison: a longer calibration window also moves the
underlying quantile model's training cutoff. It does not isolate conformal
correction length while keeping the base model identical. One earlier month
does not establish deployment performance, provide a significance test, or
resolve seasonal under-coverage. No parameters were selected on the inspected
2026 test; no candidate was promoted. A future evaluation after a frozen
candidate would be required before a new performance claim.

[Raw comparison JSON](erco-calibration-experiment/comparison.json) and both
prediction Parquets are committed. The GitHub artifact ZIP SHA-256 was verified
before extraction. The initial CI failed script line-length checks; the immediate
formatting correction passed CI run 38356442576. The experiment itself completed
successfully, independently of that formatting-only correction.
