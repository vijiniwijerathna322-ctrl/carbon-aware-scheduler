# CISO monitoring snapshot

Report generated at `2026-10-12T14:51:57Z`, using raw hours from `2026-09-28T06:00Z` through `2026-10-12T05:00Z`.

| Target | Artifact | Eligible realized hours | Coverage status | Earlier held-out MAE |
|---|---|---|---|---|
| Demand | 20261012T114946Z-decc7897 | 0 | insufficient_data | 984.78 MWh |
| Carbon | 20261012T115113Z-438177c1 | 0 | insufficient_data | 29.51 g/kWh |

Overall status is **alert**, including demand target PSI 0.3082 and KS p-value 8.62e-10. The demand reference contains 4,320 finite hours, current window 336, with 336 overlapping hours. Carbon has 23 missing current observations. Its sole eligible replay issue produces 22 current-window predictions without finite actuals; these are excluded. Recent MAE and coverage remain unavailable, rather than using pre-fit history. The stale snapshot also produces a warning.

The command returned exit code 2 and wrote strict JSON plus a self-contained HTML report under `reports/monitor_CISO.*`. These generated artifacts remain local. The endpoint serves the saved report without recomputing it; the baked Docker demo initially returns `404 {"error":"no_report"}`.

See [the isolated shift experiment](drift-simulation.md) and [ADR 0017](../adr/0017-monitoring-cutoffs-and-diagnostics.md) for detection evidence and limitations.
