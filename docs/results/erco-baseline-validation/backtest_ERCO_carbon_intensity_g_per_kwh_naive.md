# Rolling-origin backtest: ERCO / carbon_intensity_g_per_kwh

## naive

Test interval (UTC): 2026-04-13T05:00:00+00:00 to 2026-10-13T05:00:00+00:00.

Daily region-local midnight issues; refit every 30 local calendar days. Targets beyond the test end are unscored. n counts finite point pairs; n_interval counts finite observed interval pairs. Intervals are uncalibrated.

| bucket | n | n_interval | mae | coverage | mean_width | pinball_lo | pinball_hi | winkler |
|---|---|---|---|---|---|---|---|---|
| 1-6 | 1092 | 0 | 64.921794 | N/A | N/A | N/A | N/A | N/A |
| 7-24 | 3275 | 0 | 52.466601 | N/A | N/A | N/A | N/A | N/A |
| 25-48 | 4343 | 0 | 55.365525 | N/A | N/A | N/A | N/A | N/A |
| all | 8710 | 0 | 55.473616 | N/A | N/A | N/A | N/A | N/A |

- data_source: raw
- input_sha256: 5c940bc300699ef96f42853e6fd30df5b06a5b709a5fb0e1eb821a8382397b28
- limitations: Latest-revision snapshot; zero observation latency assumed; no publication-vintage archive.
- preprocessing: Pointwise raw observations; no interpolation or centered spike filtering.
- factors_sha256: 5697a2fcd173474d398380d385cd6885099815473909971d1a75c99fee8b1d64
- carbon_scope: Observed covered generation mix; partial fuel observations and excluded OTH; imports ignored.
- timezone: America/Chicago
