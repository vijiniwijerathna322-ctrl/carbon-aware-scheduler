# 05 Uncertainty and Model Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Calibrated 80% prediction intervals via conformalized quantile regression (CQR), packaged as a trainable, saveable `ForecastModel`, with a calibration report.

**Architecture:** `SplitConformalCQR` is a small pure class. `ForecastModel` composes `QuantileLgbm` + CQR and implements the `Forecaster` protocol: data ≤ `fit_end` is split chronologically into a training window and a later calibration window. A file-based registry stores versioned artifacts with metadata.

**Tech Stack:** numpy, pandas, LightGBM, joblib.

**Spec:** `specs/2026-10-11-carbon-aware-scheduler-design.md` (decisions D4, D6; §6 model artifact; §7)

## Global Constraints

- Nominal coverage 80% (`alpha = 0.2`, base quantiles 0.1 and 0.9)
- Horizon buckets for calibration: `(1,6)`, `(7,24)`, `(25,48)`
- Calibration window: the last 90 days before `fit_end`; training window = everything before it; training targets must satisfy `target_time ≤ calibration_start`
- CQR score: `s = max(q_lo − y, y − q_hi)`; correction `q̂ = quantile(scores, min(1, ceil((n+1)(1−α))/n))`; interval `[q_lo − q̂, q_hi + q̂]`
- Use the empirical inverse-CDF/order-statistic quantile: rank k = min(n, ceil((n+1)(1−α))). No interpolation or zero-based "higher" quantile. Training and evaluation retain the raw pointwise policy from ADR 0005.
- Minimum 30 calibration points per bucket, else fall back to the pooled correction and log a warning
- Artifacts loaded with `joblib` only from the local models directory (trusted); metadata keys per spec §6
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- Calibration data overlapping training data (leak) → under-estimated correction; guarded by a test
- Negative `q̂` (model over-conservative) must shrink intervals but never produce `lower > upper`
- Fewer calibration points than needed for the quantile level → must use max score (conservative), not crash
- All-NaN or constant target in a bucket → clear error or documented fallback, not silent 0 correction
- Loading a model with a different `feature_columns` than current code → explicit error naming the mismatch
- `current` pointer missing or pointing at a deleted version → `ModelNotFoundError` with remediation hint

---

### Task 1: `SplitConformalCQR`

**Files:**
- Create: `src/carbon_scheduler/models/conformal.py`
- Test: `tests/models/test_conformal.py`

**Interfaces:**
- Produces:
  - `class SplitConformalCQR: def __init__(self, alpha: float = 0.2, buckets: Sequence[tuple[int, int]] = ((1, 6), (7, 24), (25, 48)), min_points: int = 30)`
  - `def calibrate(self, lower: np.ndarray, upper: np.ndarray, y: np.ndarray, horizon: np.ndarray) -> SplitConformalCQR` (drops non-finite rows)
  - `def adjust(self, lower: np.ndarray, upper: np.ndarray, horizon: np.ndarray) -> tuple[np.ndarray, np.ndarray]`
  - attribute `corrections_: dict[tuple[int, int], float]`

- [x] **Step 1: Failing tests:**
  - `test_marginal_coverage_on_exchangeable_synthetic_data`: heteroscedastic noise, deliberately too-narrow base intervals, 20 seeds; mean coverage on a fresh test set within `[0.78, 0.82]` and every seed ≥ 0.74
  - `test_uses_finite_sample_quantile_level` (n=9, α=0.2 → level `ceil(10×0.8)/9 = 8/9`)
  - `test_too_few_points_uses_max_score` (n=2 → correction = max score)
  - `test_negative_correction_never_crosses` (over-wide input → `lower ≤ upper`)
  - `test_small_bucket_falls_back_to_pooled` (with caplog warning)
  - `test_adjust_before_calibrate_raises`
- [x] **Step 2: Run:** `uv run pytest tests/models/test_conformal.py -v` → FAIL
- [x] **Step 3: Implement** as specified in Global Constraints; when `lower > upper` after a negative correction, set both to their midpoint.
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(models): split conformal CQR calibration`

### Task 2: `ForecastModel` composite

**Files:**
- Create: `src/carbon_scheduler/models/forecast_model.py`
- Test: `tests/models/test_forecast_model.py`

**Interfaces:**
- Consumes: `QuantileLgbm`, `SplitConformalCQR`, `build_supervised`
- Produces: `class ForecastModel` implementing `Forecaster`:
  - `def __init__(self, target: str, tz: str, alpha: float = 0.2, calibration_days: int = 90, lgbm_params: Mapping[str, Any] | None = None, seed: int = 42, issue_step_h: int = 3)`
  - `fit(series, fit_end)`: `cal_start = fit_end − calibration_days`; train on rows with `target_time ≤ cal_start`; calibrate on issue times in `(cal_start, fit_end]` with `target_time ≤ fit_end`
  - `predict(series, issue_time) -> pd.DataFrame` (`lower/median/upper` conformal-adjusted; median unchanged)
  - `metadata(self) -> dict[str, Any]` (target, tz, alpha, train_end, calibration_start, fit_end, n_train, n_calibration, feature_columns, corrections)
  - `fit` returns None under the Forecaster contract. Fixed q10/q50/q90 supports only alpha=0.2. Negative-correction crossed bounds collapse to midpoint, then widen minimally to include the unchanged median. `calibration_predictions_` and `calibration_summary()` expose descriptive reused-calibration scores, never held-out performance claims.

- [x] **Step 1: Failing tests (synthetic series, 200 days):**
  - `test_calibration_window_strictly_after_training_targets` (spy: max train `target_time ≤ cal_start`, min calibration `issue_time > cal_start`)
  - `test_intervals_contain_median_and_are_ordered`
  - `test_coverage_on_synthetic_holdout_near_nominal` (within ±5 pp of 80%)
  - `test_metadata_contains_required_keys`
  - `test_fit_too_short_series_raises_clear_error` (< calibration + 30 days)
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(models): conformalized forecast model`

### Task 3: Calibration report and backtest integration (gate G4)

**Files:**
- Modify: `src/carbon_scheduler/models/evaluate.py`, `src/carbon_scheduler/models/reporting.py`, `src/carbon_scheduler/cli.py` (`--model cqr`)
- Test: `tests/models/test_evaluate.py`

**Interfaces:**
- Produces: `def coverage_table(pred: pd.DataFrame, by: Literal["horizon_bucket","hour_local","month_local"], tz: str, alpha: float = 0.2) -> pd.DataFrame` (columns `n, coverage, mean_width`); report adds three coverage tables and a one-line verdict versus the spec §7 targets.
  - `render_backtest_report(..., *, predictions_by_model: Mapping[str, pd.DataFrame] | None = None)` attaches coverage tables and G4 verdict for CQR. Backtests also write a `.json` provenance sidecar. `scripts/summarize_cqr_backtests.py` publishes held-out coverage, paired point comparisons and observed misses.

- [x] **Step 1: Failing tests:** `test_coverage_table_by_hour_has_24_rows`, `test_coverage_table_known_values`, `test_report_flags_targets_missed`
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement**, then run the CQR backtest on CISO for both targets (manual) and save to `docs/results/backtest-cqr.md`.
- [x] **Step 4: Run tests** → PASS
- [x] **Step 5: Gate G4:** overall coverage in [77%, 83%] and ≥ 70% in every bucket? If not: longer calibration window, per-hour-of-day calibration, or accept and document. Never tune on the test period.
- [x] **Step 6: Commit** `feat(models): calibration report and cqr backtest`

### Task 4: Model registry

**Files:**
- Create: `src/carbon_scheduler/models/registry.py`
- Test: `tests/models/test_registry.py`

**Interfaces:**
- Produces:
  - `class ModelNotFoundError(FileNotFoundError)`, `class ModelIncompatibleError(RuntimeError)`
  - `def save_model(model: ForecastModel, region: str, models_dir: Path, metrics: Mapping[str, Any] | None = None, data_end: pd.Timestamp | None = None) -> Path` → `models_dir/{region}/{target}/{version}/` containing `model.joblib` and `metadata.json` (adds `versions` for python/lightgbm/pandas/numpy, `trained_at` UTC ISO, `git_sha` or `"unknown"`, `metrics`); updates `models_dir/{region}/{target}/current.json` = `{"version": "<version>"}`
  - `def load_model(region: str, target: str, models_dir: Path, version: str | None = None) -> ForecastModel`
  - `def read_metadata(region: str, target: str, models_dir: Path, version: str | None = None) -> dict[str, Any]`
  - Versions are `YYYYmmddTHHMMSSZ-<8 hex chars>` to avoid same-second overwrite. Writes stage complete versions and replace current.json atomically. Digest, feature order, trusted-root containment and exact library versions (Python major/minor) are checked before loading. Nonfinite descriptive metrics become JSON null.

- [x] **Step 1: Failing tests:** `test_roundtrip_predictions_identical`, `test_metadata_has_all_spec_keys`, `test_current_pointer_updates_on_second_save`, `test_missing_model_raises_with_hint_to_run_train`, `test_incompatible_feature_columns_raises`
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement** (version string `YYYYmmddTHHMMSSZ`).
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(models): file-based model registry`

### Task 5: `train` command

**Files:**
- Modify: `src/carbon_scheduler/cli.py`
- Create: `src/carbon_scheduler/models/training.py`
- Test: `tests/models/test_training.py`

**Interfaces:**
- Produces:
  - `def train_region(region: str, settings: Settings, targets: Sequence[str] = ("demand_mwh","carbon_intensity_g_per_kwh"), fit_end: pd.Timestamp | None = None, *, lgbm_params: Mapping[str, Any] | None = None) -> dict[str, Path]` — loads pointwise raw targets per ADR 0005, fits `ForecastModel` per target with `fit_end` defaulting to the last timestamp with a finite value, computes explicitly labelled reused-calibration metrics for metadata, saves via registry and verifies identical reloaded predictions. Parameter overrides support small tests only; real CLI uses full defaults.
  - CLI `carbon-scheduler train --region CISO [--fit-end …]`

- [x] **Step 1: Failing tests:** synthetic raw parquet in `tmp_path` saves both targets and reloads, missing raw history gives an actionable ingest hint; CLI failure is also tested.
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Manual run:** `carbon-scheduler train --region CISO`; confirm `models/CISO/*/current.json` exist.
- [x] **Step 6: Commit** `feat(cli): train command`

## Definition of Done

- [x] Coverage claims in `docs/results/backtest-cqr.md` use the held-out test months only
- [x] Gate G4 passed or documented
- [x] Trained CISO artifacts exist and reload with identical predictions
- [x] ADR 0004 (CQR choice, per-bucket calibration, limits: exchangeability under drift) written; ADR 0002 already documents global quantile models
- [x] Master plan status updated


Verification on 2026-10-12: 201 passed, one live test deselected, 93.47%
coverage; ruff, formatting, mypy and offline lock checks passed. Recorded RED
module/function-absence checks before implementing conformal, composite model,
coverage table, registry and training. Regression tests additionally cover G4
miss reporting, corrupted artifacts, path escape and same-second version saves.

Held-out six-month G4: demand PASS, overall coverage 77.35%; carbon FAIL,
overall 71.57%, 7–24h bucket 69.68%. Full results and hour/month diagnostics
are in docs/results/backtest-cqr.md. ADR 0013 records the measured miss; no
test-period tuning was performed. Both CQR medians beat the weekly baseline
in all horizon buckets. Overall point MAE improvements: demand 53.40%,
carbon 24.02%. Calibration infrastructure is implemented, but carbon intervals
are not certified as nominal 80% held-out bounds.

Real train command completed for both targets. Demand fit_end is
2026-10-12 05:00 UTC; carbon's last finite observation is 2026-10-11 06:00
UTC. Current pointers exist, artifacts reload identically, and both loaded
models predict all 48 horizons from the 2026-10-12 05:00 UTC issue despite
missing recent carbon observations. Local artifacts are ignored by Git and
can be reproduced with the train command. Reused-calibration metadata metrics
are explicitly labelled and do not substitute for held-out coverage.
