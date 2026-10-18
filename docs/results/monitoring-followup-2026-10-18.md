# CISO post-fit performance: October 18

[Refresh run 39110324437](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/39110324437)
ingested current observations using the unchanged reviewed CISO models. The
monitor failed with alert exit 2 and opened
[issue 10](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/issues/10).
Artifact SHA-256 was verified before extracting the retained
[JSON](ciso-monitoring-2026-10-18/monitor_CISO.json) and HTML diagnostics.

| Post-fit metric | Demand | Carbon proxy |
|---|---:|---:|
| Unique usable realized hours | 144 | 143 |
| Coverage (nominal 80%) | 77.08% | 69.23% |
| Coverage monitor status | ok | alert |
| Binomial diagnostic p-value | 0.404105 | 0.002264 |
| Recent MAE | 1308.1872 MWh | 31.8108 gCO2e/kWh |
| Earlier baseline MAE | 999.8728 MWh | 29.1651 gCO2e/kWh |
| MAE ratio | 1.3084 | 1.0907 |

The earlier insufficient-data gate is now resolved for both targets. Coverage
uses the latest eligible forecast per realized target hour, excludes nonfinite
labels and never scores issues preceding fit_end. Demand excludes one nonfinite
row and removes 121 duplicate target rows; carbon excludes 26 and removes 145.
Baseline MAE uses 4,201 earlier forecast hours outside the current window.

Input drift flags persist, including demand rolling mean/std and all monitored
carbon inputs. Carbon interval under-coverage confirms a real acceptance failure;
collecting 100 points was not itself a coverage pass. Binomial/KS p-values remain
operational diagnostics under dependent hourly data, not independent statistical
certification. The monitor's ok status for demand is separate from a new full
held-out G4 test.

Decision: retain the approved research-only scope and existing frozen demo; do
not promote either pending retrain candidate or claim production readiness.
Keep issue 10 open for calibration investigation. Future calibration changes
require their own frozen protocol and subsequent unseen evaluation; do not tune
thresholds or retrofit the current monitored cohort to force a pass.

## CI repair

The browser recording workflow introduced an unused shell-loop variable flagged
by Linux ShellCheck (SC2034). Commit 061c79b replaces it with `_`. This changes
no model or recording behaviour. Local Ruff/format/actionlint checks passed;
the new Linux CI result is verified separately.
