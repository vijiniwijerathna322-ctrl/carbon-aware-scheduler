# Second region: ERCO execution status

ERCO is configured with `America/Chicago`, latitude 31 and longitude -99. Region metadata can be selected with `CARBON_REGIONS_PATH`. Pipeline settings are passed explicitly through storage, registry, training, backtesting, monitoring and serving; omitted CLI regions default to the first configured entry. Omitted API regions select the region served by that service. The shipped config keeps its original region first.

## Live execution attempted on 2026-10-13

`carbon-scheduler ingest --region ERCO --end 2026-10-12T05` failed after bounded retries. A credential-free host diagnostic confirmed Windows DNS error 11001 (`getaddrinfo failed`) for `api.eia.gov`; GitHub connectivity succeeded. The configured EIA key was present and was not printed. No ERCO raw file was produced. Training and evaluation require that source history and remain pending.

| Measurement | Existing first-region result | ERCO |
|---|---|---|
| Held-out demand coverage | 77.35% | unavailable |
| Held-out carbon coverage | 71.57% | unavailable |
| Mean median-strategy savings | 29.37% | unavailable |
| Mean upper-strategy savings | 27.35% | unavailable |

This is an execution record, not evidence of ERCO model generalisation. No ERCO MAE, coverage, savings or fuel-mix comparison is claimed. Emission factors were not changed without observations. Unknown fuel codes continue to raise an explicit error.

## Independent verification and remaining work

A synthetic region defined only in a temporary YAML passes ingestion with an injected EIA client, processed dataset creation, tiny-model fitting/reloading, API startup and monitoring report generation. Invalid timezones and unknown-region messages are checked. This verifies config propagation, not performance in Texas.

When EIA DNS/network access is restored, run ingestion, build-dataset, train, six-month raw CQR backtests for both targets, schedule-backtest and monitor with `--region ERCO`. Replace the unavailable entries with measured results and source provenance before marking Plan 10 Task 2 complete.
