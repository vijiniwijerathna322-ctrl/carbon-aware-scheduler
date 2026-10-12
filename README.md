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
