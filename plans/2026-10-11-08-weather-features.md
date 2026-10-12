# 08 Weather Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add weather covariates (temperature, cloud cover, solar radiation, wind) to the forecaster, and prove with an ablation whether they improve accuracy and interval quality without leakage.

**Architecture:** An Open-Meteo client with local Parquet caching produces an hourly UTC weather frame per region. `build_supervised` gains an optional `exog` frame joined on `target_time`. Training/backtest use the archive (or historical-forecast) data; serving uses the live forecast endpoint.

**Tech Stack:** httpx, pandas; no API key.

**Spec:** `docs/superpowers/specs/2026-10-11-carbon-aware-scheduler-design.md` (§3, §9 risks)

## Global Constraints

- Open-Meteo: free for non-commercial use, no key, CC BY 4.0 → attribution in README and API docs; stay below 10,000 calls/day (cache aggressively)
- Variables: `temperature_2m`, `cloud_cover`, `shortwave_radiation`, `wind_speed_100m`; units as returned (°C, %, W/m², km/h) recorded in metadata
- Region weather points come from `config/regions.yaml` (`weather_points: [{lat, lon, weight}]`, added to the existing `Region` dataclass in `src/carbon_scheduler/regions.py` as `weather_points: tuple[WeatherPoint, ...]`, default empty); frame = weighted mean across points. CISO gets three points (e.g. Los Angeles, San Francisco Bay, Fresno) weighted by approximate load share — record the rationale in ADR 0003
- Index tz-aware UTC hourly, same convention as the hourly frame
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- **Train/serve skew:** training on realized weather but serving on forecasts inflates offline accuracy; the ablation must state which source was used, and the preferred training source is Open-Meteo's *historical forecast* data if probing confirms it exists
- Missing weather hours → NaN features (model must still predict), never forward-filled silently
- Cache must not serve a stale forecast: forecast-endpoint responses are never cached longer than 1 hour; archive responses cached by (point, date-range)
- Network failure at serving time → forecasts still returned using weather-free fallback model, with `notes` saying so
- API response for 16 days of forecast must not be requested if only 48 h are needed (respect fair use)

---

### Task 1: Probe Open-Meteo and record fixtures

**Files:**
- Create: `scripts/probe_open_meteo.py`, `tests/fixtures/open_meteo/archive.json`, `…/forecast.json`, `…/historical_forecast.json`

- [ ] **Step 1: Write and run the probe** for one point and a 2-day range against the archive, forecast and historical-forecast endpoints; save raw JSON.
- [ ] **Step 2: Inspect and record** in the spec §3: endpoint URLs that work, variable names, units, timezone handling (request `timezone=UTC`), whether the historical-forecast endpoint covers 2021+ for the chosen variables.
- [ ] **Step 3: Decide the training source** (historical-forecast if coverage ≥ 2021, else archive + noted caveat) and write ADR 0003.
- [ ] **Step 4: Commit** `docs: verify open-meteo endpoints and record fixtures`

### Task 2: Weather client with cache

**Files:**
- Create: `src/carbon_scheduler/weather/__init__.py`, `src/carbon_scheduler/weather/client.py`
- Test: `tests/weather/test_client.py`

**Interfaces:**
- Produces:
  - `class WeatherClient: def __init__(self, cache_dir: Path, http: httpx.Client | None = None)`
  - `def fetch_history(self, points: Sequence[WeatherPoint], start: date, end: date, source: Literal["archive","historical_forecast"]) -> pd.DataFrame` (weighted mean over points; cached per point/range)
  - `def fetch_forecast(self, points: Sequence[WeatherPoint], hours: int = 72) -> pd.DataFrame`
  - `@dataclass(frozen=True) class WeatherPoint: lat: float; lon: float; weight: float`

- [ ] **Step 1: Failing tests (respx + fixtures):** `test_history_returns_utc_hourly_with_expected_columns`, `test_second_call_served_from_cache` (one HTTP request total), `test_weighted_mean_of_two_points`, `test_forecast_not_cached_beyond_one_hour` (inject clock), `test_http_error_raises_weather_unavailable`
- [ ] **Step 2: Run:** `uv run pytest tests/weather -v` → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(weather): open-meteo client with caching`

### Task 3: Join weather into features

**Files:**
- Modify: `src/carbon_scheduler/features/build.py`, `src/carbon_scheduler/models/forecast_model.py`
- Test: `tests/features/test_exog.py`

**Interfaces:**
- Produces:
  - `build_supervised(..., exog: pd.DataFrame | None = None)` — when given, adds its columns (prefixed `wx_`) taken at `target_time`; `FEATURE_COLUMNS` stays the base list, new function `def feature_columns(exog: pd.DataFrame | None) -> list[str]`
  - `ForecastModel(..., exog: pd.DataFrame | None = None)`; metadata gains `exog_columns` and `exog_source`

- [ ] **Step 1: Failing tests:** `test_exog_columns_joined_at_target_time`, `test_missing_weather_hours_are_nan_not_filled`, `test_no_exog_equals_previous_behaviour` (byte-equal frame to plan 04 output), `test_registry_roundtrip_keeps_exog_columns`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(features): optional exogenous weather features`

### Task 4: Ablation (weather vs no weather)

**Files:**
- Create: `scripts/ablation_weather.py`, `docs/results/ablation-weather.md`

- [ ] **Step 1: Run the CQR backtest twice** (with/without `exog`) for both targets, same config and seeds.
- [ ] **Step 2: Write the results table:** MAE, coverage, mean width, Winkler by horizon bucket; 3–5 sentences of interpretation; if training used realized weather, state the train/serve skew caveat prominently.
- [ ] **Step 3: Decision:** keep weather only if it improves MAE or interval width without breaking coverage; record in ADR 0003.
- [ ] **Step 4: Commit** `docs: weather ablation results`

### Task 5: Serve with weather and graceful fallback

**Files:**
- Modify: `src/carbon_scheduler/api/service.py`
- Test: `tests/api/test_service_weather.py`

- [ ] **Step 1: Failing tests:** `test_forecast_uses_weather_when_model_requires_it`, `test_weather_unavailable_falls_back_and_adds_note`, `test_demo_mode_uses_baked_weather_snapshot`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** (fallback = keep the weather-free model artifact alongside; demo snapshot includes the weather frame for the demo period).
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Re-run** `bash scripts/smoke_docker.sh` → PASS
- [ ] **Step 6: Commit** `feat(api): weather-aware serving with fallback`

## Definition of Done

- [ ] Ablation published with honest conclusion
- [ ] Attribution to Open-Meteo present in README and `/docs` description
- [ ] Smoke test still green; master plan status updated
