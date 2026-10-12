# 05 Uncertainty and Model Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calibrated 80% prediction intervals via conformalized quantile regression (CQR), packaged as a trainable, saveable `ForecastModel`, with a calibration report.

**Architecture:** `SplitConformalCQR` is a small pure class. `ForecastModel` composes `QuantileLgbm` + CQR and implements the `Forecaster` protocol: data ≤ `fit_end` is split chronologically into a training window and a later calibration window. A file-based registry stores versioned artifacts with metadata.

**Tech Stack:** numpy, pandas, LightGBM, joblib.

**Spec:** `docs/superpowers/specs/2026-10-11-carbon-aware-scheduler-design.md` (decisions D4, D6; §6 model artifact; §7)

## Global Constraints

- Nominal coverage 80% (`alpha = 0.2`, base quantiles 0.1 and 0.9)
- Horizon buckets for calibration: `(1,6)`, `(7,24)`, `(25,48)`
- Calibration window: the last 90 days before `fit_end`; training window = everything before it; training targets must satisfy `target_time ≤ calibration_start`
- CQR score: `s = max(q_lo − y, y − q_hi)`; correction `q̂ = quantile(scores, min(1, ceil((n+1)(1−α))/n))`; interval `[q_lo − q̂, q_hi + q̂]`
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

- [ ] **Step 1: Failing tests:**
  - `test_marginal_coverage_on_exchangeable_synthetic_data`: heteroscedastic noise, deliberately too-narrow base intervals, 20 seeds; mean coverage on a fresh test set within `[0.78, 0.82]` and every seed ≥ 0.74
  - `test_uses_finite_sample_quantile_level` (n=9, α=0.2 → level `ceil(10×0.8)/9 = 8/9`)
  - `test_too_few_points_uses_max_score` (n=2 → correction = max score)
  - `test_negative_correction_never_crosses` (over-wide input → `lower ≤ upper`)
  - `test_small_bucket_falls_back_to_pooled` (with caplog warning)
  - `test_adjust_before_calibrate_raises`
- [ ] **Step 2: Run:** `uv run pytest tests/models/test_conformal.py -v` → FAIL
- [ ] **Step 3: Implement** as specified in Global Constraints; when `lower > upper` after a negative correction, set both to their midpoint.
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(models): split conformal CQR calibration`

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

- [ ] **Step 1: Failing tests (synthetic series, 200 days):**
  - `test_calibration_window_strictly_after_training_targets` (spy: max train `target_time ≤ cal_start`, min calibration `issue_time > cal_start`)
  - `test_intervals_contain_median_and_are_ordered`
  - `test_coverage_on_synthetic_holdout_near_nominal` (within ±5 pp of 80%)
  - `test_metadata_contains_required_keys`
  - `test_fit_too_short_series_raises_clear_error` (< calibration + 30 days)
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(models): conformalized forecast model`

### Task 3: Calibration report and backtest integration (gate G4)

**Files:**
- Modify: `src/carbon_scheduler/models/evaluate.py`, `src/carbon_scheduler/models/reporting.py`, `src/carbon_scheduler/cli.py` (`--model cqr`)
- Test: `tests/models/test_evaluate.py`

**Interfaces:**
- Produces: `def coverage_table(pred: pd.DataFrame, by: Literal["horizon_bucket","hour_local","month_local"], tz: str, alpha: float = 0.2) -> pd.DataFrame` (columns `n, coverage, mean_width`); report adds three coverage tables and a one-line verdict versus the spec §7 targets.

- [ ] **Step 1: Failing tests:** `test_coverage_table_by_hour_has_24_rows`, `test_coverage_table_known_values`, `test_report_flags_targets_missed`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement**, then run the CQR backtest on CISO for both targets (manual) and save to `docs/results/backtest-cqr.md`.
- [ ] **Step 4: Run tests** → PASS
- [ ] **Step 5: Gate G4:** overall coverage in [77%, 83%] and ≥ 70% in every bucket? If not: longer calibration window, per-hour-of-day calibration, or accept and document. Never tune on the test period.
- [ ] **Step 6: Commit** `feat(models): calibration report and cqr backtest`

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

- [ ] **Step 1: Failing tests:** `test_roundtrip_predictions_identical`, `test_metadata_has_all_spec_keys`, `test_current_pointer_updates_on_second_save`, `test_missing_model_raises_with_hint_to_run_train`, `test_incompatible_feature_columns_raises`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** (version string `YYYYmmddTHHMMSSZ`).
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(models): file-based model registry`

### Task 5: `train` command

**Files:**
- Modify: `src/carbon_scheduler/cli.py`
- Create: `src/carbon_scheduler/models/training.py`
- Test: `tests/models/test_training.py`

**Interfaces:**
- Produces:
  - `def train_region(region: str, settings: Settings, targets: Sequence[str] = ("demand_mwh","carbon_intensity_g_per_kwh"), fit_end: pd.Timestamp | None = None) -> dict[str, Path]` — loads processed data, fits `ForecastModel` per target with `fit_end` defaulting to the last timestamp with a finite value, computes in-sample-calibration summary metrics for metadata, saves via registry
  - CLI `carbon-scheduler train --region CISO [--fit-end …]`

- [ ] **Step 1: Failing tests:** `test_train_region_saves_models_for_both_targets` (synthetic processed parquet in `tmp_path`), `test_train_region_without_processed_data_gives_actionable_error`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Manual run:** `carbon-scheduler train --region CISO`; confirm `models/CISO/*/current.json` exist.
- [ ] **Step 6: Commit** `feat(cli): train command`

## Definition of Done

- [ ] Coverage claims in `docs/results/backtest-cqr.md` use the held-out test months only
- [ ] Gate G4 passed or documented
- [ ] Trained CISO artifacts exist and reload with identical predictions
- [ ] ADR 0002 (CQR choice, per-bucket calibration, limits: exchangeability under drift) written
- [ ] Master plan status updated
