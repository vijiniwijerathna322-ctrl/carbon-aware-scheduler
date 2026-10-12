# 04 Forecasting Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leakage-safe features, baselines, a global LightGBM quantile forecaster and a rolling-origin backtest that proves (or disproves) the model beats seasonal-naive for demand and carbon intensity.

**Architecture:** Pure functions for metrics and features; a `Forecaster` protocol (`fit` on data ≤ `fit_end`, `predict` from data ≤ `issue_time`) implemented by baseline and LightGBM; a backtest harness that *physically truncates* the series it hands to forecasters so future data cannot leak.

**Tech Stack:** pandas, numpy, LightGBM, scikit-learn (metrics helpers only if needed).

**Spec:** `specs/2026-10-11-carbon-aware-scheduler-design.md` (decisions D2, D3, D5; §7)

## Global Constraints

- Horizons 1..48 hours: `HORIZONS = tuple(range(1, 49))`
- Targets: `demand_mwh`, `carbon_intensity_g_per_kwh`
- Seasonal anchors per D3: `anchor_24 = y[t+h-24·ceil(h/24)]`, `anchor_168 = y[t+h-168·ceil(h/168)]` (always ≤ issue time `t`)
- Quantile levels `(0.1, 0.5, 0.9)`; seed `42`; LightGBM `n_jobs` fixed for determinism
- Chronological splits only; no shuffling; no random CV
- Real evaluation uses raw observations with pointwise demand validation and carbon recomputation. Retrospective processed data is explicit exploratory mode only (ADR 0005). Latest revisions and zero reporting latency remain limitations.
- Backtest: test = last 6 months of data; issue times every 24 h at 00:00 region-local; refit every 30 days
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- **Leakage:** perturbing any value after `issue_time` must leave every feature for that issue time unchanged (explicit test)
- Backtest must never hand a forecaster data after `fit_end` (fit) or `issue_time` (predict) — spy test
- Training rows whose `target_time > fit_end` must be excluded
- Series with NaN gaps: features become NaN, rows with NaN target dropped for training, prediction still returns a row (LightGBM handles NaN)
- Local-time features across DST changes (hour 02:00 missing/doubled) must not crash or misalign
- Quantile crossing (q10 > q50) must be repaired by sorting, never returned
- Horizon > 168 for seasonal naive must raise

---

### Task 1: Metrics

**Files:**
- Create: `src/carbon_scheduler/models/__init__.py`, `src/carbon_scheduler/models/metrics.py`
- Test: `tests/models/test_metrics.py`

**Interfaces:**
- Produces (all take `np.ndarray`/`pd.Series`, ignore pairs where any input is NaN, return `float`):
  - `mae(y, pred)`
  - `pinball_loss(y, q_pred, alpha)`
  - `interval_coverage(y, lower, upper)` — fraction with `lower ≤ y ≤ upper`
  - `mean_interval_width(lower, upper)`
  - `winkler_score(y, lower, upper, alpha)` — width plus `2/alpha ×` penalty for misses

- [x] **Step 1: Failing tests** with hand-computed values: `test_mae_known`, `test_pinball_median_equals_half_mae`, `test_pinball_asymmetric_alpha_0_9` (under-prediction penalised 0.9), `test_coverage_known` (3 of 4 inside → 0.75), `test_winkler_miss_penalty`, `test_nan_pairs_ignored`, `test_empty_input_returns_nan`
- [x] **Step 2: Run** `uv run pytest tests/models/test_metrics.py -v` → FAIL
- [x] **Step 3: Implement** with numpy masks.
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(models): evaluation metrics`

### Task 2: Seasonal-naive baseline and the `Forecaster` protocol

**Files:**
- Create: `src/carbon_scheduler/models/base.py`, `src/carbon_scheduler/models/baselines.py`
- Test: `tests/models/test_baselines.py`

**Interfaces:**
- Produces:
  - `class Forecaster(Protocol)`: `def fit(self, series: pd.Series, fit_end: pd.Timestamp) -> None`; `def predict(self, series: pd.Series, issue_time: pd.Timestamp) -> pd.DataFrame` returning columns `target_time, horizon, lower, median, upper` (point-only models set `lower`/`upper` to NaN)
  - `class SeasonalNaiveForecaster: def __init__(self, season_h: int = 168, horizons: Sequence[int] = HORIZONS)` implementing it; median = `y[target_time - season_h]`. HORIZONS is defined in models/base.py and re-exported by features/build.py.

- [x] **Step 1: Failing tests:**
  - `test_uses_value_one_week_earlier` (series = index hours; assert median equals `target − 168 h` value)
  - `test_never_reads_after_issue_time` (series truncated at issue → still works for h ≤ 48)
  - `test_horizon_beyond_season_raises` (`season_h=24`, horizon 48 requested → `ValueError`)
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement.** `predict` accepts a `horizons` attribute set at construction (default `HORIZONS`).
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(models): forecaster protocol and seasonal-naive baseline`

### Task 3: Leakage-safe supervised features

**Files:**
- Create: `src/carbon_scheduler/features/__init__.py`, `src/carbon_scheduler/features/build.py`
- Test: `tests/features/test_build.py`

**Interfaces:**
- Produces:
  - `HORIZONS: tuple[int, ...]`
  - `FEATURE_COLUMNS: list[str]` = `["horizon","y_issue","y_lag1","y_lag24","roll_mean_24","roll_std_24","anchor_24","anchor_168","hour_local","dow_local","month_local","is_us_holiday"]` (calendar features describe the **target** time in region-local tz; the `y_*`, `roll_*` features describe the state at issue time)
  - `def build_supervised(series: pd.Series, issue_times: pd.DatetimeIndex, *, tz: str, horizons: Sequence[int] = HORIZONS, with_target: bool = True) -> pd.DataFrame` — long frame, one row per (issue_time, horizon): columns `issue_time`, `target_time`, `horizon`, the rest of `FEATURE_COLUMNS`, and `y` (NaN when target_time not in series or `with_target=False`)

- [x] **Step 1: Failing tests:**
  - `test_no_leakage_future_values_do_not_change_features`: build features at issue `t`; copy the series, add 1e6 to every value after `t`; assert `FEATURE_COLUMNS` frames are equal
  - `test_anchor_definitions`: for `h=5` anchor_24 equals `y[t+5-24]`; for `h=30` equals `y[t+30-48]`; `anchor_168` for `h=30` equals `y[t+30-168]`
  - `test_target_matches_series_value`
  - `test_row_count_is_issues_times_horizons`
  - `test_dst_transition_does_not_crash_and_hour_local_is_consistent` (issue times around `2024-03-10` in `America/Los_Angeles`)
  - `test_with_target_false_leaves_y_nan`
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement** vectorised with `Series.reindex` over computed timestamps (no Python loop over rows); holidays from `pandas.tseries.holiday.USFederalHolidayCalendar`.
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(features): leakage-safe supervised feature builder`

### Task 4: LightGBM quantile forecaster

**Files:**
- Create: `src/carbon_scheduler/models/lgbm.py`
- Test: `tests/models/test_lgbm.py`

**Interfaces:**
- Consumes: `build_supervised`, `FEATURE_COLUMNS`
- Produces:
  - `class QuantileLgbm: def __init__(self, alphas: Sequence[float] = (0.1, 0.5, 0.9), params: Mapping[str, Any] | None = None, seed: int = 42)`; `fit(self, X: pd.DataFrame, y: pd.Series) -> QuantileLgbm`; `predict(self, X: pd.DataFrame) -> pd.DataFrame` with columns `q10, q50, q90` sorted row-wise so `q10 ≤ q50 ≤ q90`
  - `class LgbmForecaster: def __init__(self, tz: str, alphas: Sequence[float] = (0.1, 0.5, 0.9), issue_step_h: int = 3, seed: int = 42, params: Mapping[str, Any] | None = None)` implementing `Forecaster` (`fit` builds training rows with `issue_step_h = 3`, keeps only rows with finite `y` and `target_time ≤ fit_end`; `predict` builds one issue time and returns `lower=q10, median=q50, upper=q90`). params supports small test training budgets; real backtests use defaults. Both model wrappers accept only the fixed q10/q50/q90 levels, raising clearly for other alpha sequences.

- [x] **Step 1: Failing tests (synthetic sinusoid + noise, 120 days):**
  - `test_quantiles_ordered`
  - `test_median_beats_constant_baseline_mae`
  - `test_deterministic_with_same_seed`
  - `test_training_excludes_targets_after_fit_end` (spy on `QuantileLgbm.fit` argument: no row with `target_time > fit_end`)
  - `test_predict_returns_48_rows_with_schema`
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement** with `LGBMRegressor(objective="quantile", alpha=a, n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=seed, n_jobs=1, verbose=-1)` as default params.
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(models): lightgbm quantile forecaster`

### Task 5: Rolling-origin backtest and summaries

**Files:**
- Create: `src/carbon_scheduler/models/backtest.py`, `src/carbon_scheduler/models/evaluate.py`
- Test: `tests/models/test_backtest.py`, `tests/models/test_evaluate.py`

**Interfaces:**
- Consumes: `Forecaster`, metrics
- Produces:
  - `@dataclass(frozen=True) class BacktestConfig: test_start: pd.Timestamp; test_end: pd.Timestamp; tz: str; issue_hour_local: int = 0; retrain_every_days: int = 30`
  - `def rolling_origin_backtest(series: pd.Series, make_forecaster: Callable[[], Forecaster], cfg: BacktestConfig) -> pd.DataFrame` — columns `issue_time, target_time, horizon, lower, median, upper, y`. Refit cadence uses local calendar days, not fixed elapsed hours across DST. All model horizons remain present; labels beyond test_end are NaN/unscored. Ambiguous/nonexistent custom local issue hours are skipped.
  - `def summarize(pred: pd.DataFrame, alpha: float = 0.2, buckets: Sequence[tuple[int, int]] = ((1, 6), (7, 24), (25, 48))) -> pd.DataFrame` — index = bucket label (`"1-6"`…, plus `"all"`), columns `n, n_interval, mae, coverage, mean_width, pinball_lo, pinball_hi, winkler`. n counts finite point pairs; n_interval counts finite label/lower/upper rows; width uses that same interval sample.
  - `def compare_point_forecasts(naive: pd.DataFrame, lgbm: pd.DataFrame) -> pd.DataFrame` — identical forecast keys and labels required; paired finite predictions define G3 samples. Columns n, mae_naive, mae_lgbm, improvement_percent, g3_pass by bucket plus all.

- [x] **Step 1: Failing tests:**
  - `test_fit_never_sees_data_after_fit_end` and `test_predict_never_sees_data_after_issue_time` (spy forecaster records `series.index.max()`)
  - `test_refit_cadence` (60-day test, retrain 30 → 2 fits)
  - `test_prediction_rows_match_issue_times_times_horizons`
  - `test_summarize_buckets_and_all_row`
  - `test_naive_backtest_on_periodic_series_has_zero_mae` (perfect weekly periodic series)
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement.** Issue times = local `issue_hour_local` each day converted to UTC; `fit_end` = latest issue time at or before the refit date; pass `series.loc[:fit_end]` to `fit` and `series.loc[:issue_time]` to `predict`; join `y` from the full series afterwards.
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(models): rolling-origin backtest and summaries`

### Task 6: `backtest` command and first results (gate G3)

**Files:**
- Create: `src/carbon_scheduler/models/reporting.py`
- Modify: `src/carbon_scheduler/cli.py`
- Test: `tests/models/test_reporting.py`

**Interfaces:**
- Produces:
  - `def render_backtest_report(summary_by_model: Mapping[str, pd.DataFrame], region: str, target: str) -> str` (Markdown table per model + header with date range)
  - CLI `carbon-scheduler backtest --region CISO --target carbon_intensity_g_per_kwh --model {naive,lgbm}`; writes `reports/backtest_{region}_{target}_{model}.md` and `…parquet` (predictions)
  - `load_backtest_series(region, target, settings, data_source="raw") -> tuple[pd.Series, dict[str, str]]` returns pointwise targets and provenance. `run_backtest(region, target, model, settings, *, reports_dir=Path("reports"), data_source="raw", test_start=None, test_end=None) -> Path` uses the latest six calendar months; shorter fixtures reserve the first 168 hours as seasonal history. CLI exposes `--reports-dir` and `--data-source {raw,processed}`. `scripts/summarize_point_backtests.py` publishes paired comparisons and local hour/month diagnostics from all four saved prediction files.

- [x] **Step 1: Failing tests:** `test_report_contains_all_buckets_and_model_names`, `test_cli_backtest_naive_on_fixture_dataset_writes_report` (tiny processed parquet fixture, `tmp_path` as data dir)
- [x] **Step 2: Run** → FAIL
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Run on real CISO data (manual)** for both targets and both models. Record the table in `docs/results/backtest-point.md`.
- [x] **Step 6: Gate G3:** LightGBM median MAE < seasonal-naive MAE on paired finite predictions in every bucket for both targets? If not: examine errors by hour/month and check leakage. Select any feature/hyperparameter changes only on a pre-test chronological validation period, then re-run and retain the original result. Do not proceed to plan 05 until this holds or you have an ADR explaining why not.
- [x] **Step 7: Commit** `feat(cli): backtest command and first results`

## Definition of Done

- [x] All tasks done; leakage and truncation tests green
- [x] `docs/results/backtest-point.md` committed with real numbers
- [x] Gate G3 passed (or ADR explains)
- [x] Master plan status updated


Verification on 2026-10-12: tasks 1–5 committed locally after
RED module-absence checks and GREEN implementation checks. Task 6 CLI tests
are green; all four real CISO backtests completed with unchanged default parameters.
Local gate: 184 passed, one live test deselected, 95.70% coverage; ruff, format,
mypy and offline lock validation passed.

G3 PASS: six-calendar-month test 2026-04-12 05:00 to 2026-10-12 05:00 UTC,
183 daily local-midnight issues, seven refits per model. Paired MAE improved
53.35% for demand overall (2690.36 → 1255.11 MWh), with bucket improvements
73.44%, 60.49%, 44.35%; carbon improved 38.49% overall (43.98 → 27.05
gCO2e/kWh), with bucket improvements 55.20%, 46.41%, 27.90%. Recorded full
metrics, sample counts, hour/month diagnostics, versions, parameters and input
digests in docs/results/backtest-point.md. No test-period tuning was performed.
Raw interval coverage is 73.17% for demand and 58.83% for carbon; Plan 05
calibration remains necessary. Raw snapshot evaluation still assumes latest
revisions and zero observation latency, as documented in ADR 0005.
