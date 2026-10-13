# 10 Automation and Second Region Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the system fresh and trustworthy without manual work (scheduled ingest + monitor, human-reviewed retraining, image publishing) and prove the pipeline generalises by running a second balancing authority (ERCO, Texas).

**Architecture:** GitHub Actions workflows call the existing CLI commands. Retraining opens a pull request (human review gate) instead of pushing models to `main`. Region-specific values live only in `config/regions.yaml`.

**Tech Stack:** GitHub Actions, GHCR, Dependabot, existing CLI.

**Spec:** `specs/2026-10-11-carbon-aware-scheduler-design.md` (§2 v1, §8)

## Global Constraints

- Repo is public (free Actions minutes); `EIA_API_KEY` stored as an Actions secret; workflows using it run only on `schedule`, `workflow_dispatch`, or pushes to `main` — never on pull requests from forks
- Scheduled refresh weekly (cron `0 6 * * 1` UTC); data cached with `actions/cache` keyed by region
- Third-party actions pinned to a major version or commit SHA; workflow `permissions:` set to least privilege per job
- Image published to `ghcr.io/<owner>/carbon-aware-scheduler` only on tags `v*`
- Second region: `ERCO` with `timezone: America/Chicago`; no region name hard-coded in `src/` outside tests and `config/regions.yaml`
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- Secret must never appear in logs: workflow echoes nothing from env; `set +x`; confirm via a dry-run log review
- A monitor `alert` must fail the scheduled job visibly (exit code 2) and create an issue, but must not auto-retrain on `main`
- Retrain PR must include metrics diff vs previous model; merging a worse model should be obvious from the diff
- EIA outage during scheduled run → job fails with a clear message, no partial data written (ingest writes atomically: temp file then rename)
- ERCO has different fuel codes/gaps → factor check raises `UnknownFuelError` rather than mis-computing
- Tag push must not publish if CI on that commit is red

---

### Task 1: Atomic writes for stores

**Files:**
- Modify: `src/carbon_scheduler/ingest/store.py`, `src/carbon_scheduler/models/registry.py`
- Test: `tests/ingest/test_store_atomic.py`

- [x] **Step 1: Regression tests:** interrupted serialization/replacement and successful cleanup for hourly stores and registry pointers.
- [x] **Step 2: Existing implementation audit:** atomic writes already implemented; no redundant implementation or red-first claim.
- [x] **Step 3: Confirm** same-directory temporary files, os.replace and finally cleanup in both existing implementations.
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `test(store): verify atomic writes preserve previous snapshots`

### Task 2: Regions config generalisation and ERCO run

**Files:**
- Modify: `config/regions.yaml`, `src/carbon_scheduler/regions.py` (exists from plan 02/08), `src/carbon_scheduler/config.py` (add `regions_path`)
- Test: `tests/test_region_configuration.py`
- Create: `docs/results/second-region-erco.md`

**Interfaces:**
- Consumes: `Region`, `load_regions(path)` from plan 02/08
- Produces: `Settings.regions_path: Path` (env `CARBON_REGIONS_PATH`, default `config/regions.yaml`) and every pipeline function reading regions through it, so tests can point at a temp YAML

- [x] **Step 1: Failing tests:** `test_load_regions_validates_timezone` (invalid tz name rejected), `test_unknown_region_error_lists_known_codes`, `test_pipeline_runs_for_synthetic_region_defined_only_in_temp_yaml` (proves no hard-coding)
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement**; add ERCO entry.
- [x] **Step 4: Run** → PASS
- [ ] **Step 5: Manual run:** `ingest`, `build-dataset`, `train`, `backtest --model cqr`, `schedule-backtest`, `monitor` for `ERCO`. Fix `emission_factors.yaml` if new fuel codes appear (ERCO has more wind, little hydro).
- [ ] **Step 6: Write `docs/results/second-region-erco.md`:** side-by-side CISO vs ERCO table (MAE vs naive, coverage, savings) and what differs and why.
- [ ] **Step 7: Commit** `feat: second region ERCO and region config loader`

### Task 3: Scheduled refresh workflow

**Files:**
- Create: `.github/workflows/refresh.yml`

- [x] **Step 1: Write the workflow:** triggers `schedule` + `workflow_dispatch`; matrix over `[CISO, ERCO]`; steps: checkout, setup-uv, restore cache for `data/`, `uv sync --frozen`, `ingest`, `build-dataset`, `monitor` (non-zero on alert), upload `reports/` as artifact, save cache; on failure of `monitor` create a GitHub issue via `gh issue create` with the report reasons (job-level `permissions: issues: write`).
- [x] **Step 2: Validate syntax:** `uv run python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/refresh.yml'))"` → no error; also review with `actionlint` if installed.
- [ ] **Step 3: Add the `EIA_API_KEY` secret** in the repo settings (you do this yourself) and run the workflow via `workflow_dispatch`; confirm artifact appears and the log contains no key.
- [x] **Step 4: Commit** `ci: scheduled refresh and monitoring workflow`

### Task 4: Retrain-by-PR workflow

**Files:**
- Create: `.github/workflows/retrain.yml`, `scripts/metrics_diff.py`
- Test: `tests/scripts/test_metrics_diff.py`

**Interfaces:**
- Produces: `def metrics_diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> str` (Markdown table of metric, old, new, delta)

- [ ] **Step 1: Failing tests:** `test_diff_shows_deltas_and_marks_regressions`, `test_missing_old_metrics_handled`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** the script; workflow (`workflow_dispatch` only): ingest, build-dataset, train, backtest, `make-demo`, then open a PR (`peter-evans/create-pull-request`, pinned) with branch `retrain/<date>` and the metrics diff in the PR body.
- [ ] **Step 4: Run tests** → PASS; dispatch the workflow once and check the PR body.
- [ ] **Step 5: Commit** `ci: retrain workflow that opens a reviewable PR`

### Task 5: Release workflow and dependency hygiene

**Files:**
- Create: `.github/workflows/release.yml`, `.github/dependabot.yml`

- [ ] **Step 1: Write `release.yml`:** on tag `v*`; jobs: `needs` the CI workflow result (`workflow_run` or re-run the gate), then `docker/build-push-action` to GHCR with tags `latest` and the version; `permissions: packages: write, contents: read`.
- [ ] **Step 2: Write `dependabot.yml`:** weekly updates for `pip` (uv) and `github-actions`.
- [ ] **Step 3: Tag `v0.2.0` and push;** verify the image appears in GHCR and `docker run ghcr.io/<owner>/carbon-aware-scheduler:0.2.0` passes `scripts/smoke_docker.sh` (parameterise the script by image name).
- [ ] **Step 4: Commit** `ci: release workflow and dependabot`

## Definition of Done

- [ ] Weekly refresh ran successfully at least once; artifact reviewed
- [ ] A retrain PR was produced and reviewed
- [ ] Published image runs the smoke test
- [ ] ERCO results documented; master plan status updated

## Execution record: Task 1

The executing-plans sub-skill is not installed; the plan is followed directly. Task 1 already had same-directory temporary writes, os.replace and finally cleanup in both hourly storage and registry pointers. Six regression cases now exercise interrupted Parquet serialization, interrupted pointer serialization, replacement failures for both stores, successful replacement and cleanup. Existing implementations were retained. Quality evidence is recorded after the gate completes; Tasks 2?5 remain pending.

Task 1 gate: ruff check, ruff format check and mypy passed; full suite 301 passed, 1 deselected, coverage 92.95%.

## Task 2 execution amendments

Config propagation and ERCO metadata are implemented; full ERCO evaluation is pending EIA DNS recovery (Windows getaddrinfo error 11001 on 2026-10-13). The published second-region record explicitly leaves metrics unavailable. Task 2 is not complete. Tests use a unique filename to avoid collision with existing ingestion region tests. Store/registry/report writer interfaces add optional keyword-only regions_path arguments; settings-aware callers pass the configured path. CLI omission selects the first config entry, preserving the shipped ordering; API omission selects the service's region. No region identifiers remain hard-coded in src. Existing test doubles accept the new keyword arguments. Tests exercised the changes and failures were fixed before publication.

Task 2 code verification: 307 tests passed, 1 deselected, 93.08% coverage; ruff, formatting and mypy green. Synthetic custom-region API requests without an explicit region and saved monitoring status also passed. Live ERCO measurements remain pending and Task 2 is not marked complete.

## Task 3 execution record

Implemented refresh.yml with Monday 06:00 UTC scheduling, manual dispatch, independent region jobs, locked uv setup, isolated data cache restore/save, ingestion, dataset construction, monitoring, always-on diagnostics and issue creation on monitor failure. Alert exits remain job failures. Completed ingestion is saved after alerts; failed ingestion is not cached. No retraining or model promotion occurs.

Fresh runners require reviewed model and earlier held-out baseline artifacts because local ignored models/reports are absent from checkout. Region-specific MODELS_RUN_ID variables select successful main-branch runs; artifacts from pull-request runs are rejected. A public artifact inventory on 2026-10-13 found no monitoring-models-CISO or monitoring-models-ERCO bundles. Live dispatch, artifact review and live secret-log review remain pending prerequisites; Task 3 Step 3 is not complete. Operations are documented in docs/automation-refresh.md.

Verification: YAML and embedded Python parsed; official checksum-verified actionlint 1.7.12 passed all workflows; actionlint validation added to CI. Ruff, formatting and mypy passed; full suite 307 passed, 1 deselected, coverage 93.08%.
