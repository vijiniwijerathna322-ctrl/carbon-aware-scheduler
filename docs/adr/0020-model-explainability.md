# ADR 0020: Local feature attribution via native TreeSHAP contributions

## Context

The forecasting models (`QuantileLgbm`, three `LGBMRegressor` boosters per
target for quantiles 0.1/0.5/0.9) had no way to explain an individual
forecast: why the median landed where it did, or which inputs drove it. A
portfolio-worthy forecasting system should let a reviewer inspect a
prediction, not just trust it.

## Decision

Use LightGBM's own `Booster.predict(X, pred_contrib=True)` (TreeSHAP
contributions, computed natively, in C++) on the median (q50) booster rather
than adding the general-purpose `shap` package as a dependency. This needed
no new dependency, and since `pred_contrib` returns exact Shapley values for
the exact tree ensemble actually served, there is no model-fidelity gap to
disclose.

`QuantileLgbm.median_contributions` (`models/lgbm.py`) wraps the raw call;
`ForecastModel.explain` (`models/forecast_model.py`) builds the same feature
frame `predict` uses (factored out into a shared `_feature_frame` helper so
the two paths can't drift apart) and returns a tidy per-feature table;
`models/explain.py`'s `explain_forecast` ranks and truncates to the top-N
contributions per horizon, while still summing *all* contributions (not just
the displayed top-N) plus the base value to report `raw_median` — verified in
tests to reproduce the booster's own raw prediction.

**Scope, stated in the API response's own `notes` and here:**
- Explains the **raw median quantile model's output before conformal
  calibration** — `SplitConformalCQR`'s offset (see ADR 0004) is a single
  undifferentiated correction, not attributable to individual features.
- Explains the median booster specifically, not the lower/upper quantile
  boosters, and not interval width.
- Uses the weather-free baseline model even when an approved weather variant
  is being served for that target (ADR 0016) — a second, cheaper caveat than
  tracking which model variant actually served each request.
- Is a **local** (per-forecast) explanation; it is not a global
  feature-importance view across the model's lifetime.
- Technically also precedes `predict`'s quantile-crossing repair
  (`np.sort` across the three boosters' outputs) — in practice this only
  differs from the served median on the rare rows where crossing occurred.

A real serving bug surfaced while building this: `QuantileLgbm.feature_columns_`
is absent on some already-persisted model artifacts (predating that field),
and `_features()` already tolerated this via `getattr(..., FEATURE_COLUMNS)`
fallback — but the first version of `median_contributions` and `explain`
accessed the attribute directly, raising `AttributeError` against the real
baked demo models while every synthetic-data unit test (which trains fresh
models) passed cleanly. Found only by running the live demo end-to-end before
writing this ADR, not by unit tests. Fixed by using the same fallback
pattern, and `tests/api/test_api_baked_demo.py` now calls
`/v1/forecast/explain` against the real tracked artifacts specifically to
catch this class of regression in CI going forward.

## Consequences

`/v1/forecast/explain` and the Streamlit "Why this forecast?" panel are
available with zero new runtime dependencies. The CV-facing claim is
deliberately narrow: this explains one specific number (the raw median), not
the full calibrated interval or the model's general behavior. Future weather
variants or alternate quantile targets would need their own pass through this
same scope question before being added to the explanation surface.
