# 02 Data Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull EIA-930 hourly demand, forecast, generation, interchange and per-fuel generation for a region into a validated, gap-free hourly Parquet dataset, with incremental updates.

**Architecture:** A thin `EiaClient` (pagination, retry, throttle) → route-specific fetchers → pure transform to a wide hourly frame → pure validation/cleaning that returns a `QualityReport` → Parquet store. CLI `ingest` orchestrates.

**Tech Stack:** httpx, tenacity, pandas, pyarrow, respx (tests).

**Spec:** `specs/2026-10-11-carbon-aware-scheduler-design.md` (§3 Data sources, §6 Data contracts)

## Global Constraints

- Python `>=3.11,<3.13`; timestamps tz-aware UTC; units MWh
- EIA key only via env `EIA_API_KEY`; never logged; passed as `api_key` query parameter
- EIA JSON page cap: 5,000 rows → `length=5000`, paginate with `offset`
- Hourly `period` format believed `YYYY-MM-DDTHH` (UTC) — **verified in Task 1 before use**
- No network in unit tests; recorded fixtures under `tests/fixtures/eia/`
- Gate per task: ruff check, ruff format --check, mypy src, pytest
- Conventional Commits

## Review Focus

- API returns numeric values as strings and sometimes `null` → parsed to float/NaN, never crash
- Duplicate `(period, type)` rows (revisions) → keep the last, count them
- DST/timezone: everything UTC; a local-time period must never leak in
- HTTP 429/5xx → bounded retry with backoff; HTTP 403/invalid key → immediate `EiaAuthError`, no retry loop
- Empty response (no data in range) → empty frame with correct columns, not an exception
- Re-running `ingest` twice yields an identical file (idempotent); EIA revising a recent hour replaces the stored value
- Spikes (e.g. demand ×10) and negative demand are flagged and set to NaN, and counted in the report

---

### Task 1: Probe the live API and record fixtures (gate G1)

**Files:**
- Create: `scripts/probe_eia.py`, `tests/fixtures/eia/region_data_page.json`, `tests/fixtures/eia/fuel_type_data_page.json`, `tests/fixtures/eia/route_meta_region_data.json`, `tests/fixtures/eia/route_meta_fuel_type_data.json`
- Modify: `specs/…-design.md` §3 (replace the "Unverified assumptions" paragraph with verified facts)

**Interfaces:** Produces verified constants used below: `REGION_DATA_ROUTE = "electricity/rto/region-data"`, `FUEL_TYPE_ROUTE = "electricity/rto/fuel-type-data"`, set of `fueltype` codes, set of `type` codes (`D`, `DF`, `NG`, `TI` expected), exact `period` format.

- [x] **Step 1: Get a free key** at the EIA registration page; put it in `.env` (not committed).
- [x] **Step 2: Write `scripts/probe_eia.py`:** GET `https://api.eia.gov/v2/electricity/rto/region-data/` (route metadata: facets, frequencies, data columns) and `…/fuel-type-data/`; then GET each `/data/` with `frequency=hourly&data[0]=value&facets[respondent][]=CISO&start=2024-01-01T00&end=2024-01-02T00&length=5000&sort[0][column]=period&sort[0][direction]=asc`. Save raw JSON (with the `api_key` stripped from any echoed URL) into the four fixture files.
- [x] **Step 3: Run it:** `uv run python scripts/probe_eia.py` → Verified: four route/page files plus two facet-code files written, all HTTP 200. Full 5000 limit records every category at both inclusive boundaries.
- [x] **Step 4: Inspect and record** in the spec §3: actual `period` format, facet names, `type` and `fueltype` codes, whether `value` is a string, whether `start`/`end` are inclusive, and `response.total`. If anything contradicts the plan's interfaces below, fix this plan first (gate G1).
- [x] **Step 5: Commit** `docs: verify EIA API shape and record fixtures` (commit `15384ce`).

### Task 2: `EiaClient` with pagination, retry and throttle

**Files:**
- Create: `src/carbon_scheduler/ingest/__init__.py`, `src/carbon_scheduler/ingest/eia_client.py`
- Test: `tests/ingest/test_eia_client.py`

**Interfaces:**
- Produces:
  - `class EiaAuthError(RuntimeError)`, `class EiaRequestError(RuntimeError)`
  - `class EiaClient: def __init__(self, api_key: str, *, base_url: str = "https://api.eia.gov/v2", http: httpx.Client | None = None, page_length: int = 5000, min_interval_s: float = 0.25, max_retries: int = 5, sleep: Callable[[float], None] = time.sleep) -> None`
  - `def fetch_route(self, route: str, *, facets: Mapping[str, Sequence[str]], start: str, end: str, data: Sequence[str] = ("value",), frequency: str = "hourly") -> list[dict[str, Any]]` — all rows across pages

- [x] **Step 1: Failing tests (respx)** — names and assertions:
  - `test_paginates_until_total`: `total=12000`, pages of 5000/5000/2000 → `len(rows) == 12000`, three requests with `offset` 0/5000/10000
  - `test_retries_on_429_then_succeeds`: first response 429, second 200 → rows returned, 2 requests
  - `test_gives_up_after_max_retries`: persistent 503 with `max_retries=2` → `EiaRequestError`, 3 requests
  - `test_invalid_key_raises_auth_error_without_retry`: 403 → `EiaAuthError`, exactly 1 request
  - `test_api_key_never_logged`: caplog contains no key text
- [x] **Step 2: Run:** `uv run pytest tests/ingest/test_eia_client.py -v` → FAIL
- [x] **Step 3: Implement** with `tenacity` (`retry_if_exception_type(_Retryable)`, exponential backoff with jitter, `sleep` injectable so tests don't wait) and a simple monotonic-clock throttle ensuring `min_interval_s` between requests (set to 0 in tests).
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(ingest): EIA client with pagination, retry and throttle` (commit `0a5b4dc`).

### Task 3: Route fetchers

**Files:**
- Create: `src/carbon_scheduler/ingest/fetchers.py`
- Test: `tests/ingest/test_fetchers.py`

**Interfaces:**
- Consumes: `EiaClient.fetch_route`
- Produces:
  - `def fetch_region_data(client: EiaClient, respondent: str, start: str, end: str) -> pd.DataFrame` — columns `period` (datetime64[ns, UTC]), `type` (str), `value` (float, NaN for null)
  - `def fetch_fuel_type_data(client: EiaClient, respondent: str, start: str, end: str) -> pd.DataFrame` — columns `period`, `fueltype`, `value`

- [x] **Step 1: Failing tests** using the recorded fixtures through a stub client:
  - `test_region_data_parses_utc_and_numeric`: dtype of `period` is `datetime64[ns, UTC]`; `value` dtype float64
  - `test_null_value_becomes_nan`
  - `test_empty_response_returns_typed_empty_frame`: columns present, zero rows
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement** both functions; period parsing uses the format verified in Task 1; `pd.to_numeric(errors="coerce")` for `value`.
- [x] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(ingest): region and fuel-type fetchers`

### Task 4: Transform to a wide hourly frame

**Files:**
- Create: `src/carbon_scheduler/ingest/transform.py`
- Test: `tests/ingest/test_transform.py`

**Interfaces:**
- Produces: `def to_hourly_frame(region: pd.DataFrame, fuel: pd.DataFrame) -> tuple[pd.DataFrame, int]` — returns the frame and the number of duplicate rows dropped. Frame: tz-UTC hourly `DatetimeIndex` named `period`, columns `demand_mwh` (type D), `demand_forecast_mwh` (DF), `net_generation_mwh` (NG), `net_interchange_mwh` (TI), and `gen_<fueltype.lower()>_mwh` per fuel; index reindexed to a complete hourly range (gaps → NaN).

- [ ] **Step 1: Failing tests:**
  - `test_pivots_types_to_columns`
  - `test_duplicates_keep_last_and_are_counted` (two rows same period/type → later one wins, count == 1)
  - `test_index_is_complete_hourly_utc` (a missing hour appears as NaN row)
  - `test_unknown_type_ignored_not_crash`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** with `pivot_table(aggfunc="last")` after explicit de-dup so the count is known.
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(ingest): wide hourly frame transform`

### Task 5: Validation and cleaning with a quality report

**Files:**
- Create: `src/carbon_scheduler/ingest/validate.py`
- Test: `tests/ingest/test_validate.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class QualityReport: n_rows: int; n_negative_demand: int; n_spikes: int; n_interpolated: int; n_remaining_gaps: int; gap_fraction: float`
  - `def validate_and_clean(df: pd.DataFrame, *, spike_z: float = 8.0, max_gap_hours: int = 3) -> tuple[pd.DataFrame, QualityReport]` — returns a copy; never mutates input. Rules: demand ≤ 0 → NaN; robust z-score (median/MAD over a 7-day centred rolling window, per column among `demand_mwh` and `net_generation_mwh`) above `spike_z` → NaN; NaN runs ≤ `max_gap_hours` linearly interpolated; longer runs stay NaN.

- [ ] **Step 1: Failing tests:**
  - `test_negative_demand_becomes_nan_and_counted`
  - `test_spike_flagged` (inject ×10 at one hour in a sinusoid → NaN then interpolated; `n_spikes == 1`)
  - `test_short_gap_interpolated_long_gap_kept` (2 h interpolated, 5 h stays NaN; counts match)
  - `test_input_not_mutated`
  - `test_clean_data_unchanged` (smooth series → report all zero except `n_rows`)
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** as above.
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(ingest): validation and cleaning with quality report`

### Task 6: Parquet store and incremental `ingest` command

**Files:**
- Create: `src/carbon_scheduler/ingest/store.py`, `src/carbon_scheduler/ingest/pipeline.py`
- Modify: `src/carbon_scheduler/cli.py` (add `ingest`)
- Test: `tests/ingest/test_store.py`, `tests/ingest/test_pipeline.py`

**Interfaces:**
- Produces:
  - `def write_hourly(df: pd.DataFrame, region: str, stage: Literal["interim","processed"], data_dir: Path) -> Path`
  - `def read_hourly(region: str, stage: Literal["interim","processed"], data_dir: Path) -> pd.DataFrame` (raises `FileNotFoundError` with a hint to run `ingest`)
  - `def run_ingest(region: str, start: str, end: str | None, settings: Settings, client: EiaClient | None = None, overlap_hours: int = 48) -> QualityReport` — if an interim file exists, fetch from `max(index) - overlap_hours`, merge with the new data (new wins), re-validate the merged frame, write.
  - `@dataclass(frozen=True) class Region: code: str; timezone: str; lat: float; lon: float` and `def load_regions(path: Path = Path("config/regions.yaml")) -> dict[str, Region]` in `src/carbon_scheduler/regions.py` (validates the IANA timezone; unknown code lookups raise `UnknownRegionError` listing known codes). Plans 08 and 10 extend this (weather points, second region).
  - CLI: `carbon-scheduler ingest --region CISO --start 2021-01-01T00 [--end …]`

- [ ] **Step 1: Failing tests:**
  - `test_write_read_roundtrip_preserves_index_tz_and_dtypes`
  - `test_ingest_is_idempotent` (run twice with a stub client → equal frames)
  - `test_ingest_revision_replaces_recent_value` (second run returns a changed value inside the overlap → stored value updated)
  - `test_incremental_fetches_from_overlap_start` (stub client records `start` argument)
  - `test_cli_ingest_without_key_fails_with_clear_message`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.** Region codes validated against `config/regions.yaml` (create it with `CISO` now: `timezone: America/Los_Angeles`, `lat: 36.7`, `lon: -119.4`).
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Live check (opt-in):** `EIA_API_KEY=… uv run carbon-scheduler ingest --region CISO --start 2021-01-01T00` → Expected: file `data/interim/CISO/hourly.parquet`, report logged; gap_fraction < 0.02 (gate G2). Add this as `tests/ingest/test_live.py` marked `live`.
- [ ] **Step 6: Commit** `feat(ingest): parquet store and incremental ingest command`

## Definition of Done

- [ ] Task 1 facts recorded in spec; fixtures committed
- [ ] `ingest` produces CISO hourly data from 2021 with `gap_fraction < 0.02`, or an ADR chooses another region (G2)
- [ ] Re-running `ingest` makes no changes
- [ ] Quality gate green; master plan status updated
