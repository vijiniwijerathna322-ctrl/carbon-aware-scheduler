# Rolling-origin backtest: ERCO / demand_mwh

## naive

Test interval (UTC): 2026-04-13T05:00:00+00:00 to 2026-10-13T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. Intervals are uncalibrated.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1098 | 0 | 3241.374317 | N/A | N/A | N/A | N/A | N/A |
| 7-24 | 3293 | 0 | 4623.109019 | N/A | N/A | N/A | N/A | N/A |
| 25-48 | 4367 | 0 | 4252.425922 | N/A | N/A | N/A | N/A | N/A |
| all | 8758 | 0 | 4265.045787 | N/A | N/A | N/A | N/A | N/A |

- data_source: raw
- input_sha256: 5c940bc300699ef96f42853e6fd30df5b06a5b709a5fb0e1eb821a8382397b28
- limitations: Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.
- preprocessing: Pointwise raw observations; no interpolation or centered spike filtering.
- timezone: America/Chicago
