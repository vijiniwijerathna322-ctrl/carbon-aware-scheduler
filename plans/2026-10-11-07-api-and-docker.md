# 07 API and Docker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** A FastAPI service that returns calibrated forecasts and schedule recommendations, packaged in a small, non-root Docker image that runs offline from a baked demo snapshot.

**Architecture:** `ForecastService` owns model loading and data access (injected via FastAPI dependencies, so tests swap it). Routes are thin: validate → call service/optimizer → serialise. Demo assets (`demo/data/raw`, `demo/models`) are produced by a `make-demo` CLI command and committed (small).

**Tech Stack:** FastAPI, uvicorn, pydantic v2, httpx (TestClient), Docker.

**Spec:** `specs/2026-10-11-carbon-aware-scheduler-design.md` (decision D8, §6)

## Global Constraints

- Endpoints: `GET /healthz`, `GET /v1/forecast?region=CISO&target=…&horizon=48`, `POST /v1/schedule`, `GET /v1/models/current`
- Response times in UTC ISO-8601 with `Z`; every forecast response includes `issue_time`, `data_as_of`, `model_version`, `alpha`
- Staleness: if `now − data_as_of > MAX_DATA_AGE_HOURS` (default 6) → HTTP 503 `{"error":"data_stale"}`, unless `DEMO_MODE=1`
- `horizon` ∈ [1, 48]; unknown region → 404; invalid body → 422 (FastAPI default shape)
- Docker: pinned slim Python base, multi-stage, non-root user, `HEALTHCHECK`, no secrets baked, `.dockerignore` excludes `data/`, `models/`, `.env`
- Container env: `CARBON_DATA_DIR=/app/demo/data`, `CARBON_MODELS_DIR=/app/demo/models`, `DEMO_MODE=1`
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- Model artifact missing at startup → service starts but `/healthz` reports unhealthy (503) with the reason; it must not crash-loop silently
- Schedule request whose deadline lies beyond the forecast horizon → 422 with a message stating the max horizon, not a 500
- `earliest_start` in the past relative to `issue_time` → clamp to first forecast hour and say so in the response (`notes`)
- Naive datetimes in the request → 422
- Concurrency: two simultaneous requests must not share mutable state (service is read-only after load)
- Error responses never include stack traces or filesystem paths
- Container runs as non-root and works with a read-only root filesystem (writable only `/tmp`)

---

### Task 1: App factory, schemas and health

**Files:**
- Create: `src/carbon_scheduler/api/__init__.py`, `src/carbon_scheduler/api/main.py`, `src/carbon_scheduler/api/schemas.py`, `src/carbon_scheduler/api/deps.py`
- Test: `tests/api/test_health.py`

**Interfaces:**
- Produces:
  - `def create_app(service_factory: Callable[[], ForecastService] | None = None) -> FastAPI`
  - `get_service()` dependency returning the app-scoped `ForecastService`
  - schemas: `ForecastPoint(target_time: datetime, horizon: int, lower: float, median: float, upper: float)`, `ForecastResponse(region, target, issue_time, data_as_of, model_version, alpha, points: list[ForecastPoint])`, `ScheduleRequest(region: str = "CISO", duration_hours: int, power_kw: float, earliest_start: datetime | None, deadline: datetime, strategy: Literal["median","upper"] = "median", interruptible: bool = False)`, `ScheduleResponse(recommendation: Recommendation, forecast_issue_time: datetime, data_as_of: datetime, model_version: str, notes: list[str])`

- [x] **Step 1: Failing tests:** `test_healthz_ok_with_stub_service`, `test_healthz_503_when_models_missing_includes_reason`, `test_openapi_lists_all_endpoints`
- [x] **Step 2: Run:** `uv run pytest tests/api/test_health.py -v` → FAIL
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(api): app factory, schemas and health endpoint`

### Task 2: `ForecastService`

**Files:**
- Create: `src/carbon_scheduler/api/service.py`
- Test: `tests/api/test_service.py`

**Interfaces:**
- Consumes: `load_model`, `read_metadata`, `load_backtest_series` (raw target policy)
- Produces: `class ForecastService`:
  - `def __init__(self, settings: Settings, region: str = "CISO")` (loads both targets' models and the raw snapshot once)
  - `def forecast(self, target: str, horizon: int = 48) -> tuple[pd.DataFrame, ForecastMeta]` — `issue_time` = last timestamp with a finite value of `target`
  - `@dataclass(frozen=True) class ForecastMeta: issue_time: pd.Timestamp; data_as_of: pd.Timestamp; model_version: str; alpha: float`
  - `def is_healthy(self) -> tuple[bool, str]`

- [x] **Step 1: Failing tests (tiny synthetic data + trained tiny model in a session fixture):**
  - `test_forecast_returns_horizon_rows_and_meta`
  - `test_issue_time_is_last_finite_observation`
  - `test_unknown_target_raises_value_error`
  - `test_is_healthy_false_when_no_model`
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(api): forecast service`

### Task 3: Forecast and schedule endpoints

**Files:**
- Create: `src/carbon_scheduler/api/routes.py`
- Modify: `src/carbon_scheduler/api/main.py`
- Test: `tests/api/test_routes.py`

**Interfaces:**
- Consumes: `ForecastService.forecast`, `recommend`
- Produces: the endpoints in Global Constraints; `/v1/schedule` always plans on the `carbon_intensity_g_per_kwh` forecast

- [x] **Step 1: Failing tests (FastAPI `TestClient`, stub service):**
  - `test_forecast_ok_schema_and_horizon`
  - `test_forecast_horizon_out_of_range_422`
  - `test_unknown_region_404`
  - `test_schedule_ok_returns_recommendation`
  - `test_schedule_deadline_beyond_horizon_422_mentions_max_horizon`
  - `test_schedule_naive_datetime_422`
  - `test_schedule_past_earliest_start_is_clamped_with_note`
  - `test_stale_data_503_unless_demo_mode`
  - `test_error_body_has_no_traceback_or_paths`
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement** (domain errors mapped via exception handlers: `InsufficientForecastError` → 422, `ModelNotFoundError` → 503, stale → 503).
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(api): forecast and schedule endpoints`

### Task 4: Demo assets and `make-demo`

**Files:**
- Create: `src/carbon_scheduler/demo.py`; `demo/` (generated, committed)
- Modify: `src/carbon_scheduler/cli.py`
- Test: `tests/test_demo.py`

**Interfaces:**
- Produces: `def make_demo_assets(region: str, settings: Settings, out_dir: Path, history_days: int = 400) -> None` — copies the last `history_days` of raw data and the `current` model versions for both targets into `out_dir/data` and `out_dir/models`, preserving the directory layout the loaders expect; CLI `carbon-scheduler make-demo --region CISO`

- [x] **Step 1: Failing tests:** `test_demo_assets_load_with_service` (assets produced from the synthetic fixture can be loaded by `ForecastService`), `test_demo_data_truncated_to_history_days`
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Generate** `demo/` from real CISO artifacts; check total size (`du -sh demo`, expect only a few MB) and commit it with a note on EIA attribution in `demo/README.md`.
- [x] **Step 6: Commit** `feat: demo assets for offline serving`

### Task 5: Dockerfile and container smoke test

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `scripts/smoke_docker.sh`
- Modify: `.github/workflows/ci.yml` (add docker build + smoke job), `Makefile` (`docker-build`, `docker-run`)

- [x] **Step 1: Write `scripts/smoke_docker.sh`:** build image, run detached with `--read-only --tmpfs /tmp -p 8000:8000`, poll `/healthz` up to 30 s, `curl` `/v1/forecast?horizon=6` and a `POST /v1/schedule`, assert HTTP 200 and JSON keys `points` / `recommendation`, stop container; exit non-zero on any failure.
- [x] **Step 2: Run it before writing the Dockerfile** — `bash scripts/smoke_docker.sh` → Expected: FAIL (no image)
- [x] **Step 3: Write the Dockerfile:** stage 1 `python:3.11-slim` + uv, `uv sync --frozen --no-dev` into `/app/.venv`; stage 2 copies venv, `src/`, `config/`, `demo/`; `useradd` non-root; env vars per Global Constraints; `HEALTHCHECK` using Python `urllib` (no curl dependency); `CMD ["uvicorn","carbon_scheduler.api.main:app","--host","0.0.0.0","--port","8000"]` (module-level `app = create_app()`).
- [x] **Step 4: Run** `bash scripts/smoke_docker.sh` → Expected: PASS; also `docker image ls` to note the image size (target < 600 MB)
- [x] **Step 5: Add the CI job** and push; confirm green.
- [x] **Step 6: Commit** `build: dockerfile, smoke test and CI job`

### Task 6: API documentation in the OpenAPI schema and README quickstart

**Files:**
- Modify: `src/carbon_scheduler/api/schemas.py` (field descriptions + `json_schema_extra` examples), `README.md`

- [x] **Step 1: Failing test:** `test_openapi_examples_present_for_schedule_request` (inspect `app.openapi()`)
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement**; README quickstart: `docker run -p 8000:8000 …`, two `curl` examples with real output pasted, link to `/docs`.
- [x] **Step 4: Run tests** → PASS; follow the README commands verbatim in a clean shell to confirm they work.
- [x] **Step 5: Commit** `docs(api): openapi examples and quickstart`

## Definition of Done (= MVP line)

- [x] `bash scripts/smoke_docker.sh` passes on a clean Linux Docker host in CI; native local API checks pass
- [x] README quickstart works verbatim from a clean clone, no API key
- [x] All MVP DoD items in the master plan §2 met
- [x] Tag `v0.1.0`; master plan status updated

## Implementation and verification status

- Complete: API, immutable startup service, raw demo assets, Dockerfile, smoke test, CI and quickstart. App/service/routes were integrated because their startup dependencies are coupled.
- Serving and demo follow the raw training policy (ADR 0015). Both target models and carbon factor configuration are validated before serving.
- Native quality gate: 255 tests passed, 93.37% coverage; Ruff, formatting, mypy and lock consistency passed.
- Final branch commit 30359fb passed both Linux quality and Docker smoke jobs in [CI run 38251774540](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/38251774540).
- Docker verification used a fresh Linux CI checkout: non-root user, read-only root filesystem, offline demo, health, forecast and schedule. Image size 587,311,058 bytes, below the 600 MB target. The development Windows machine has no Docker runtime; the clean CI Docker host supplies the container verification required for release.
- Initial cross-platform failures were corrected: NumPy pinned to artifact version 2.4.6; demo/factor bytes preserved in Git; Windows staging inherits workspace ACLs.
- User authorized publication to the configured GitHub repository. MVP merged to local main and tagged locally as v0.1.0. Remote main/tag publication awaits explicit user approval after automatic review rejected it (feature-branch authorization did not cover the default branch).
- Regression tests were developed alongside portions of implementation; separate red-phase commits were not made for every task. Carbon G4 remains a documented miss and no nominal job-level confidence guarantee is claimed.
