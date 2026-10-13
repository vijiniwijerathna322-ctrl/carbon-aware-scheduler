# ADR 0017: Monitoring cutoffs and diagnostic limits

## Context

D9 requires input drift, realized interval coverage and error monitoring. Replaying a newly fitted artifact over issues before its fit cutoff would score training or calibration history as if it were held out. Hourly observations and rolling features are also dependent.

## Decision

Use a 180-day reference ending at each artifact's fit cutoff and a 14-day current raw window. Report finite and excluded counts, reference overlap, source hashes and both model versions. PSI uses reference quantiles with explicit handling of ties and constant samples; KS uses a 0.01 threshold. Both require 100 finite samples.

Replay daily local-midnight issues only at or after `fit_end`, with inputs physically truncated to the issue. Score one latest eligible forecast per realized target hour. Coverage uses the two-sided exact binomial test against 0.8 with at least 100 observations. MAE compares with earlier, configuration-matched, raw-target held-out CQR predictions, excluding the current window. Calibration scores and archive-weather experiments are not valid baselines.

Unavailable metrics are JSON null with `insufficient_data`; status precedence is alert, warn, insufficient_data, ok. Stale snapshots produce a warning. Approved weather deployments require issue-vintage forecast logs and are rejected by this baseline replay monitor until those logs exist. Reports are atomically replaced; the API returns explicit missing or invalid report errors. Reports contain no credentials.

## Consequences

Recently fitted models can have no eligible realized predictions. Input alarms can still occur, but they do not establish coverage failure. Reference and current windows can overlap; overlap is disclosed. Serial dependence, ties, seasonality and multiple tests make p-values operational diagnostics rather than calibrated alarm probabilities. Latest-revision snapshots assume zero observation latency. A healthy synthetic weekly pattern tests the coverage alarm independently of seasonality; the real-data simulation retains its pre-existing input alarms.

The statistical definitions follow the official SciPy documentation for [binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html) and [ks_2samp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html). Monitoring does not repair the previously documented carbon coverage gate miss.
