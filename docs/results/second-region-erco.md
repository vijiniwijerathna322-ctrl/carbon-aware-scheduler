# Second region: ERCO execution status

ERCO is configured with `America/Chicago`, latitude 31 and longitude -99. Region metadata can be selected with `CARBON_REGIONS_PATH`. Pipeline settings are passed explicitly through storage, registry, training, backtesting, monitoring and serving; omitted CLI regions default to the first configured entry. Omitted API regions select the region served by that service. The shipped config keeps its original region first.

## Earlier local execution attempt on 2026-10-13

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

The initial unavailable measurements above describe the local attempt only. Live-runner results and retained reports below supersede that execution blocker; final acceptance remains subject to the observed coverage and monitoring limitations.

## Live runner recovery and measured replay (2026-10-13)

GitHub runner run 38349279499 completed real ERCO ingestion, fitting, held-out evaluation and quality checks. Draft PR 7 retains the candidate. Demand coverage is 74.72% and carbon coverage 79.48%; demand 25-48-hour coverage is 73.99%, so review the G4 tolerance before promotion. These are rolling-origin results, not validation of the final fitted artifact.

Replay validation run 38354149330 used the exact retained raw cache and candidate forecasts with matching input/factor provenance. Median savings were 20.872840%, upper 17.947653%, and oracle 22.880929%, on 2,726 of 2,760 illustrative jobs per strategy; 34 lacked complete actual windows. These are average generation-proxy scenario savings, not measured avoided emissions. See [full replay](erco-validation/schedule_backtest_ERCO.md).

The [monitor report](erco-validation/monitor_ERCO.json) records alert status and input drift flags. Both targets have zero usable post-fit realized points, so current coverage and MAE are insufficient-data, not successful performance acceptance. Monitor exit 2 is retained separately. The validation workflow succeeds at collecting diagnostics; it does not assert healthy operation or promote the model.

The retained runner report contained an inherited CISO-specific carbon-G4-failure sentence. The committed report corrects that sentence to region-independent coverage-review wording; numeric results and provenance are unchanged. The report generator is corrected likewise. ERCO full refresh acceptance, promotion review and release remain pending.
