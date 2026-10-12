# ADR 0003: Issue-time feature boundary

## Context

Decision D3 requires features available at the forecast issue, including horizons
beyond one daily cycle and calendar transitions across daylight-saving time.

## Decision

Use UTC instants for indexing. Seasonal anchors use
`target_time - season_hours * ceil(horizon / season_hours)`, which never exceeds
issue_time. Issue value, one-hour and 24-hour lags, and 24-value trailing mean
and sample standard deviation describe observations at the issue. Rolling
features require all 24 observed values; missing observations remain NaN.

Calendar features describe the target in the configured region timezone:
hour, weekday, month and US federal holiday indicator. Holidays use the local
calendar date, including observed dates. Convert UTC to local time for each
target; duplicate or nonexistent local hours do not alter UTC target alignment.

Build the long feature frame vectorially. Perturbing values after an issue is
tested to leave all its features unchanged; labels may change.

## Consequences

Daily anchors beyond 24 hours repeat the most recently available daily cycle
rather than reading a future lag. Missing features are passed to LightGBM.
Timezone conversion respects DST, while seasonal anchors remain elapsed UTC
hours. Holidays describe federal observed dates rather than a complete
California electricity-demand holiday calendar.
