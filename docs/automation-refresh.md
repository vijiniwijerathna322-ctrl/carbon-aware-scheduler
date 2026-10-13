# Weekly refresh operations

The refresh workflow runs Monday at 06:00 UTC (11:30 Asia/Colombo) once it is on the default branch, and also supports manual dispatch. Its independent region jobs ingest, build the processed dataset and monitor existing deployed models. An alert preserves the failing job status, uploads JSON/HTML diagnostics, saves successfully ingested history and opens an issue. Command errors also open a monitoring failure issue. Ingest or dataset failures upload available quality diagnostics but do not masquerade as a model alert. No training or model promotion occurs.

## Prerequisites

Configure the repository Actions secret `EIA_API_KEY`. It is passed only to prerequisite checking and ingestion; shell tracing is disabled and the CLI's request-log redaction remains active. Configure repository variables `CISO_MODELS_RUN_ID` and `ERCO_MODELS_RUN_ID` with reviewed model deployment runs in this repository. Each referenced run must have completed successfully on `main`, without a pull-request trigger.

The selected run must publish an artifact named `monitoring-models-<REGION>`, with these paths at its root:

```text
models/<REGION>/<TARGET>/current.json
models/<REGION>/<TARGET>/<VERSION>/model.joblib
models/<REGION>/<TARGET>/<VERSION>/metadata.json
reports/backtest_<REGION>_<TARGET>_cqr.parquet
reports/backtest_<REGION>_<TARGET>_cqr.json
```

Include both demand and carbon targets. Models must be raw-target, weather-free artifacts compatible with the locked runtime; baselines must be earlier held-out CQR results with matching configuration. The monitor validates the baseline contract and reports insufficient data if the results cannot be used. Exclude existing `monitor_<REGION>.*` reports and credentials. A clean runner verifies the source run and model compatibility before using the bundle. GitHub artifacts expire, so keep the variables pointed at retained reviewed deployments. Local ignored `models/` and `reports/` are not automatically available on GitHub.

## Failure and persistence behavior

Data caches are isolated by region and use a unique run/attempt key with a region-specific restore prefix. Only raw and interim history is cached; model selection comes from the reviewed bundle. A completed ingestion is cached even if subsequent monitoring alerts; failed ingestion is not cached. The current ingestion implementation checkpoints complete yearly route pairs atomically, so an upstream failure can leave earlier complete local years, but never an incomplete Parquet replacement. Such checkpoints are not published into the scheduled cache after a failed ingestion.

Reports and quality diagnostics are uploaded with 30-day retention even when the run fails. The monitor's exit code 2 remains a job failure. The issue body is written to a file, includes report reasons and a link to the run, and does not execute report text as shell commands. Each failed monitor run creates one issue per affected region; repeated alerts can create repeated issues.

## Validation status

Workflow syntax and local quality checks are recorded in Plan 10. CISO run 38354869293 completed ingestion/build, retained diagnostics and opened issue 8 after monitor alert exit 2. Artifact digest and reports were reviewed; no secret value was printed. ERCO history, candidate models and evaluations now exist, but no reviewed ERCO deployment bundle is approved. The workflow fails with explicit prerequisite errors rather than treating missing deployments as healthy monitoring.

The artifact transport follows the official [download-artifact contract](https://github.com/actions/download-artifact) and cache behavior follows [actions/cache](https://github.com/actions/cache).

Prepare an explicit local bundle for review with `uv run python scripts/prepare_deployment.py --region CISO --output .tools/deployment-CISO-review`. The script validates selected model compatibility and baseline configuration, copies only an allowlist and records exact file hashes. It does not upload or approve the bundle. Authenticated GitHub access is needed for publication and dispatch. ADR 0018 allows verified workflow code onto main before live acceptance, while Plan 10 remains in progress.

The dedicated deployment-bundle.yml publisher now packages the existing main-reviewed CISO demo model bytes with committed frozen held-out baselines. Without an explicit region run-ID override, refresh/retrain discovers retained matching artifacts only from successful main runs of that publisher; PR runs, expired artifacts and other-region bundles are excluded. ERCO has no approved bundle yet. Discovery is not a model promotion mechanism.
