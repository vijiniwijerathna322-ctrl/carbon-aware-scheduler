# Weather ablation: exploratory realized-weather covariates

**This uses archive/reanalysis weather at future target times. It is a hindsight sensitivity experiment, not leakage-free deployment evidence. Train/serve skew remains: live weather forecasts have errors not represented here. No weather model will be promoted from these results.**

Provider: [Open-Meteo](https://open-meteo.com/), CC BY 4.0. Four variables at three illustrative CISO points; missing hours/cells remain NaN. Historical Forecast probes had no 100 m wind in January 2021, and seamless history is not an issue-vintage 48-hour forecast panel.

MAE, mean width and Winkler are in MWh for demand and gCO2e/kWh for intensity. Coverage in the tables is a fraction. Evaluation uses daily local-midnight issues over 2026-04-12 through 2026-10-12, seven 30-day refits, 90-day calibration, 400 trees, seed 42 and one training thread. Finite paired rows are shared by both variants; absent target labels are excluded, not filled.

## demand_mwh

Input SHA-256: `1c09b875ae857d5962070f40c23dc00910f3e5d6095a550d2fb13a41805e3bd7`. Weather snapshot SHA-256: `0a7f6d736f1bbc478f0b72ae9834a8897f53f95851ffeea34f6bea50663f3873`.

| bucket | n | mae | coverage | mean_width | winkler |
|---|---|---|---|---|---|
| base/1-6 | 1098 | 421.167551 | 0.863388 | 1622.397631 | 2006.550866 |
| base/7-24 | 3292 | 1218.007322 | 0.750608 | 3667.057950 | 5867.642596 |
| base/25-48 | 4366 | 1489.956425 | 0.768209 | 4323.871788 | 7175.262948 |
| base/all | 8756 | 1253.685681 | 0.773527 | 3738.164870 | 6035.480849 |
| weather/1-6 | 1098 | 452.113865 | 0.886157 | 1877.630175 | 2130.997264 |
| weather/7-24 | 3292 | 1167.336613 | 0.725091 | 3254.108705 | 5471.512313 |
| weather/25-48 | 4366 | 1183.710955 | 0.761338 | 3552.152019 | 5861.093936 |
| weather/all | 8756 | 1085.812606 | 0.763362 | 3230.111867 | 5246.869536 |

Baseline reused: True; identical input hashes, seed, parameters, refit configuration, forecast keys and labels verified.

Overall MAE changes from 1253.69 to 1085.81 (-13.39%). Coverage changes from 77.35% to 76.34%; mean width changes from 3738.16 to 3230.11. G4's nominal 80% acceptance range is 77%-83%. These are hindsight-weather measurements and cannot validate live accuracy.

## carbon_intensity_g_per_kwh

Input SHA-256: `1c09b875ae857d5962070f40c23dc00910f3e5d6095a550d2fb13a41805e3bd7`. Weather snapshot SHA-256: `0a7f6d736f1bbc478f0b72ae9834a8897f53f95851ffeea34f6bea50663f3873`.

| bucket | n | mae | coverage | mean_width | winkler |
|---|---|---|---|---|---|
| base/1-6 | 1092 | 24.683115 | 0.777473 | 81.498749 | 118.745334 |
| base/7-24 | 3275 | 30.143745 | 0.696794 | 89.233088 | 126.284041 |
| base/25-48 | 4343 | 38.071846 | 0.714483 | 115.328488 | 160.387585 |
| base/all | 8710 | 33.412256 | 0.715729 | 101.275157 | 142.343676 |
| weather/1-6 | 1092 | 33.702610 | 0.751832 | 91.168400 | 137.575654 |
| weather/7-24 | 3275 | 34.026784 | 0.684580 | 89.678998 | 131.014171 |
| weather/25-48 | 4343 | 41.344347 | 0.707575 | 112.907101 | 163.606695 |
| weather/all | 8710 | 37.634841 | 0.704478 | 101.447779 | 148.088163 |

Baseline reused: True; identical input hashes, seed, parameters, refit configuration, forecast keys and labels verified.

Overall MAE changes from 33.41 to 37.63 (+12.64%). Coverage changes from 71.57% to 70.45%; mean width changes from 101.28 to 101.45. G4's nominal 80% acceptance range is 77%-83%. These are hindsight-weather measurements and cannot validate live accuracy.

## Decision

Retain the weather-free production models. These exploratory differences cannot establish operational improvement because future realized weather was supplied at prediction time. Carbon coverage must still be judged against G4; changing features on this previously examined test interval is not independent confirmation. An issue-vintage weather panel and a fresh holdout are required before promotion. Existing demo/API artifacts stay weather-free and offline.
