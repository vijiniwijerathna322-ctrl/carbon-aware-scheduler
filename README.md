# Carbon-Aware Energy Scheduler

[![CI](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/workflows/ci.yml)

Forecast grid demand and carbon intensity, then schedule flexible jobs with honest uncertainty.
Implementation follows the [master plan](plans/2026-10-11-00-master-plan.md).

## Development

Use Python 3.11 or 3.12 and uv. Run `uv sync`, then `make check`.
On Windows without make, run `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy src`, and `uv run pytest -q`.
Copy `.env.example` to `.env` for local configuration; never commit API keys.
Run `uv run carbon-scheduler --help` or `uv run carbon-scheduler version`.
Defaults and relative directory overrides resolve against the project root; absolute
`CARBON_DATA_DIR` and `CARBON_MODELS_DIR` overrides are also supported.
Live tests are excluded by default; explicitly select them with `uv run pytest -m live`.

## Ingest hourly data

Set `EIA_API_KEY` in the ignored project `.env`, then run:

```powershell
uv run carbon-scheduler ingest --region CISO --start 2021-01-01T00
```

Long histories are fetched in adjacent calendar-year windows to keep API queries bounded.
Completed windows are checkpointed as raw observations. If a later request fails,
rerun the same command to resume with a 48-hour overlap. Cleaned interim output and
its quality report update after the entire requested interval succeeds. Historical
backfills before the existing cache start update raw only after full success, so
an interrupted backfill retries its older prefix safely.

`--end YYYY-MM-DDTHH` optionally limits the inclusive UTC interval. Raw observations and cleaned interim Parquet files live under
`data/<stage>/CISO/`; the interim directory also
contains `quality-report.json`. Reruns refresh a 48-hour overlap; revised nulls remain
missing. The CLI prints cleaning counts and G2 status. G2 requires less than 2% of
hours incomplete across the four core series; fuel completeness is reported separately. G2 failure exits with code 2 and retains
the data for inspection.

Live verification on 2026-10-12 covered 2021-01-01 00:00 through 2026-10-12
05:00 UTC: 50,646 hourly rows, 623 incomplete core hours (1.2301%), and G2 passed.
An identical 48-hour-overlap rerun preserved the raw/interim Parquet and quality
report bytes. Fuel coverage remains separate: GEO first appears on 2025-12-16
09:00 UTC, and missing historical observations are retained rather than inferred.

The full-history live check is explicitly opt-in and downloads into a temporary directory:

```powershell
uv run pytest tests/ingest/test_live.py -m live --no-cov
```

## Build the carbon dataset

After ingestion, run `uv run carbon-scheduler build-dataset --region CISO`.
This offline command writes `data/processed/CISO/hourly.parquet` and
`carbon-quality-report.json` without requiring an API key. Use `--factors-path`
to select another validated factors file; relative paths resolve from the project root.
Equal reruns preserve both files' bytes and modification times.

Intensity is a lifecycle proxy for observed positive generation with configured
factors. Storage, unknown fuels and heterogeneous OTH are excluded; imports are
not attributed. Missing fuel observations remain missing. The output includes
covered/excluded generation, observed coverage, missing included fuel-cell counts
and negative generation counts. Observed coverage does not measure unobserved
generation. The report records factors, citations, absent fuel codes and input digests.
See [ADR 0001](docs/adr/0001-generation-based-intensity.md).

The [executed EDA notebook](notebooks/01_eda.ipynb) includes local-calendar profiles,
missingness and distributions. Regenerate it from the project root with:

```powershell
uv sync --group eda
uv run --group eda python scripts/build_eda_notebook.py
```

The 50,646-hour snapshot has mean intensity 237.16 gCO2e/kWh and 47 missing
intensity hours. Its 29.37–449.03 range reflects changing observed fuel mixes.
43,472 hours have partial included-fuel observations, largely because GEO appears
late; these values must not be described as complete whole-grid carbon intensity.

## Forecast backtests

Run offline rolling-origin comparisons on the latest six calendar months:

```powershell
uv run carbon-scheduler backtest --region CISO --target demand_mwh --model naive
uv run carbon-scheduler backtest --region CISO --target demand_mwh --model lgbm
uv run carbon-scheduler backtest --region CISO --target carbon_intensity_g_per_kwh --model naive
uv run carbon-scheduler backtest --region CISO --target carbon_intensity_g_per_kwh --model lgbm
uv run python scripts/summarize_point_backtests.py
```

Reports and prediction Parquet files go to `reports/`; `--reports-dir` overrides
that directory. The final comparison is written to `docs/results/backtest-point.md`.
Forecasts cover horizons 1–48, with daily region-local midnight issues and refits
every 30 local calendar days. LightGBM uses fixed seed 42 and one CPU thread.

Backtests default to raw observations, preserving gaps and avoiding the future
information used by retrospective cleaning. They still use latest revisions and
assume zero observation latency. `--data-source processed` enables exploratory
retrospective results and does not establish leakage-safe performance. Point
scores compare identical forecast rows for G3; reports also show per-model
availability and uncalibrated interval metrics. See [ADR 0005](docs/adr/0005-chronological-raw-backtest.md).

The [first six-month results](docs/results/backtest-point.md) pass G3 in every
horizon bucket for both targets. Paired overall median MAE improved by 53.35%
for demand (2,690.36 → 1,255.11 MWh) and 38.49% for carbon intensity
(43.98 → 27.05 gCO2e/kWh). Raw interval coverage is 73.17% and 58.83%,
respectively; these intervals still need Plan 05 calibration.
