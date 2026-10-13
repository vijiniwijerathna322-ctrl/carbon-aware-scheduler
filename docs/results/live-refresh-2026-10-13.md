# CISO live refresh validation

[Run 38354869293](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/actions/runs/38354869293)
used the existing reviewed CISO bundle, resolved automatically from the retained
publisher. Bundle validation, EIA ingestion, processed dataset creation,
post-alert cache save, diagnostic upload and failure-issue creation succeeded.

Monitoring returned alert exit 2, correctly failing the job. Input PSI/KS drift
flags were reported for both targets. There were only 22 demand and 23 carbon
post-fit realized hours, below the minimum 100, so coverage and recent MAE
cannot establish performance acceptance.

[Issue 8](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/issues/8)
contains the actual reasons and links to the diagnostic run. Downloaded reports
are retained in `ciso-refresh-validation/`; the artifact ZIP SHA-256 was verified
before extraction. No model was retrained or promoted. This validates the live
alert path, not healthy operation.

Manual refresh supports `region=CISO`, `region=ERCO` or `region=all`. Scheduled
refresh still selects both. ERCO has no approved deployment bundle and remains
blocked at that prerequisite until candidate review and separate promotion.
Do not use a failed retrain run as a deployment source or suppress monitor alerts
to make acceptance look green.
