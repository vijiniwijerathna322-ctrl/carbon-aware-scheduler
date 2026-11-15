# 08 Weather Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add weather covariates (temperature, cloud cover, solar radiation, wind) to the forecaster, and measure an explicitly exploratory archive-weather ablation. Operational proof is deferred until issue-vintage forecast data and a fresh holdout are available.

**Architecture:** An Open-Meteo client with local Parquet caching produces an hourly UTC weather frame per region. `build_supervised` gains an optional `exog` frame joined on `target_time`. Exploratory training/backtest use archive data; approved serving variants require issue-vintage training provenance and weather available by the reported issue. Production remains weather-free.

**Tech Stack:** httpx, pandas; no API key.

**Spec:** `specs/2026-10-11-carbon-aware-scheduler-design.md` (§3, §9 risks)

## Global Constraints

- Open-Meteo: free for non-commercial use, no key, CC BY 4.0 → attribution in README and API docs; stay below 10,000 calls/day (cache aggressively)
- Variables: `temperature_2m`, `cloud_cover`, `shortwave_radiation`, `wind_speed_100m`; units as returned (°C, %, W/m², km/h) recorded in metadata
- Region weather points come from `config/regions.yaml` (`weather_points: [{lat, lon, weight}]`, added to the existing `Region` dataclass in `src/carbon_scheduler/regions.py` as `weather_points: tuple[WeatherPoint, ...]`, default empty); frame = weighted mean across points. CISO gets three points (e.g. Los Angeles, San Francisco Bay, Fresno) with illustrative geographic weights, not measured load shares — record the rationale in ADR 0016
- Index tz-aware UTC hourly, same convention as the hourly frame
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- **Train/serve skew:** training on realized weather but serving on forecasts inflates offline accuracy; the ablation must state which source was used, and operational training requires a verified issue-vintage forecast panel, not seamless historical weather
- Missing weather hours → NaN features (model must still predict), never forward-filled silently
- Cache must not serve a stale forecast: forecast-endpoint responses are never cached longer than 1 hour; archive responses cached by (point, date-range)
- Network failure at serving time → forecasts still returned using weather-free fallback model, with `notes` saying so
- API response for 16 days of forecast must not be requested if only 48 h are needed (respect fair use)

---

### Task 1: Probe Open-Meteo and record fixtures

**Files:**
- Create: `scripts/probe_open_meteo.py`, `tests/fixtures/open_meteo/archive.json`, `…/forecast.json`, `…/historical_forecast.json`

- [x] **Step 1: Write and run the probe** for one point and a 2-day range against the archive, forecast and historical-forecast endpoints; save raw JSON.
- [x] **Step 2: Inspect and record** in the spec §3: endpoint URLs that work, variable names, units, timezone handling (request `timezone=UTC`), whether the historical-forecast endpoint covers 2021+ for the chosen variables.
- [x] **Step 3: Decide the training source** (historical-forecast if coverage ≥ 2021, else archive + noted caveat) and write ADR 0016.
- [x] **Step 4: Commit** `docs: verify open-meteo endpoints and record fixtures`

### Task 2: Weather client with cache

**Files:**
- Create: `src/carbon_scheduler/weather/__init__.py`, `src/carbon_scheduler/weather/client.py`
- Test: `tests/weather/test_weather_client.py`

**Interfaces:**
- Produces:
  - `class WeatherClient: def __init__(self, cache_dir: Path, http: httpx.Client | None = None)`
  - `def fetch_history(self, points: Sequence[WeatherPoint], start: date, end: date, source: Literal["archive","historical_forecast"]) -> pd.DataFrame` (weighted mean over points; cached per point/range)
  - `def fetch_forecast(self, points: Sequence[WeatherPoint], hours: int = 48, *, issue_time: pd.Timestamp | None = None) -> pd.DataFrame`
  - Optional issue_time requests exactly issue+1 through issue+hours using start_hour/end_hour; without it, forecast_hours is bounded. Received-at metadata must be no later than the serving issue.
  - `@dataclass(frozen=True) class WeatherPoint: lat: float; lon: float; weight: float`

- [x] **Step 1: Fixture tests with httpx.MockTransport:** `test_history_returns_utc_hourly_with_expected_columns`, `test_second_call_served_from_cache` (one HTTP request total), `test_weighted_mean_of_two_points`, `test_forecast_not_cached_beyond_one_hour` (inject clock), `test_http_error_raises_weather_unavailable`
- [x] **Step 2: Review boundary contracts**; red-first sequencing was not performed (see execution notes).
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(weather): open-meteo client with caching`

### Task 3: Join weather into features

**Files:**
- Modify: `src/carbon_scheduler/features/build.py`, `src/carbon_scheduler/models/forecast_model.py`
- Test: `tests/features/test_exog.py`

**Interfaces:**
- Produces:
  - `build_supervised(..., exog: pd.DataFrame | None = None)` — when given, adds its columns (prefixed `wx_`) taken at `target_time`; `FEATURE_COLUMNS` stays the base list, new function `def feature_columns(exog: pd.DataFrame | None) -> list[str]`
  - `ForecastModel(..., exog: pd.DataFrame | None = None)`; metadata gains `exog_columns` and `exog_source`

- [x] **Step 1: Add contract tests:** `test_exog_columns_joined_at_target_time`, `test_missing_weather_hours_are_nan_not_filled`, `test_no_exog_equals_previous_behaviour` (byte-equal frame to plan 04 output), `test_registry_roundtrip_keeps_exog_columns`
- [x] **Step 2: Review boundary contracts**; red-first sequencing was not performed (see execution notes).
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(features): optional exogenous weather features`

### Task 4: Ablation (weather vs no weather)

**Files:**
- Create: `scripts/ablation_weather.py`, `docs/results/ablation-weather.md`

- [x] **Step 1: Compare CQR backtests** with/without `exog` for both targets, same config and seeds. `--reuse-baseline` verifies previous report provenance/parameters and exact forecast keys/labels before reuse.
- [x] **Step 2: Write the results table:** MAE, coverage, mean width, Winkler by horizon bucket; 3–5 sentences of interpretation; if training used realized weather, state the train/serve skew caveat prominently.
- [x] **Step 3: Decision:** no promotion from hindsight data; vintage validation must improve MAE or interval width without breaking coverage; record in ADR 0016.
- [x] **Step 4: Commit** `docs: weather ablation results`

### Task 5: Serve with weather and graceful fallback

**Files:**
- Modify: `src/carbon_scheduler/api/service.py`
- Test: `tests/api/test_service_weather.py`

- [x] **Step 1: Add contract tests:** `test_forecast_uses_weather_when_model_requires_it`, `test_weather_unavailable_falls_back_and_adds_note`, `test_demo_mode_uses_baked_weather_snapshot`
- [x] **Step 2: Review boundary contracts**; red-first sequencing was not performed (see execution notes).
- [x] **Step 3: Implement** (fallback = retain the weather-free current artifact; optional weather.json approval pointer selects a vintage-trained variant. Demo reads a baked forecast frame only when a weather variant is supplied. Shipped demo remains weather-free because no variant is promoted).
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Re-run in Linux CI** `bash scripts/smoke_docker.sh` → PASS
- [x] **Step 6: Commit** `feat(api): weather-aware serving with fallback`

## Definition of Done

- [x] Ablation published with honest conclusion
- [x] Attribution to Open-Meteo present in README and `/docs` description
- [x] Smoke test still green; master plan status updated

## Execution notes

The named executing-plans sub-skill is unavailable in this environment; implementation followed the plan directly. Existing tests were preserved and new feature/client/service contract tests were added. No claim is made that a red-first test run preceded every implementation edit. See ADR 0016 for the amended provenance and optional-serving contract.

## Verified completion (2026-10-12)

- Public archive, historical and live probes recorded; explicit next-48-hour live range also verified.
- Cached annual weather snapshot: 50,664 hours, zero missing cells in the downloaded four-variable weighted frame; SHA recorded in the report.
- Both full CQR weather runs finished: seven chronological refits per target, paired cohorts of 8,756 demand and 8,710 intensity rows. Existing weather-free reports reused only after provenance/configuration/key/label checks.
- Demand MAE -13.39%, coverage 76.34%; carbon MAE +12.64%, coverage 70.45%. Retain production weather-free models; archive-weather results are hindsight evidence.
- Final local gate: 272 tests, 93.03% coverage, ruff/format/mypy pass.
- Linux quality and offline Docker smoke passed for final serving code 6329b19: https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/38259556710 . Local Docker is unavailable; smoke was run in GitHub Actions.
- Saved predictions regenerated the numerical report using --reuse-baseline --reuse-weather, with unchanged weather SHA and paired labels.
