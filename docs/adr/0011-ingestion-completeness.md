# Ingestion completeness and fuel reporting coverage

## Context

The ingestion plan requires a missingness gate below 2%, but does not define its
denominator. A live CISO sample from January 2021 contains eight fuel categories;
a sample from October 2026 also contains GEO. Its absence from earlier responses
does not prove zero geothermal generation. Pooling all cells would make the gate
depend on how many fuel categories the API happens to report.

## Decision

Measure `gap_fraction` as the fraction of hourly rows with any missing value among
the four required regional series: demand, day-ahead demand forecast, net
generation and net interchange. `n_remaining_gaps` counts those incomplete hours.
A missing required column counts as missing for every hour. The production
pipeline checks the complete requested hourly interval, including boundary hours,
and the live gate also requires a nonempty result.

Retain every observed fuel category and retain missing fuel values as NaN. Report
full-range missing-cell counts by column, first and last observed timestamps, and
missing cells between those observations. These are reporting diagnostics, not
proof that missing boundary values are structural or zero. Count interpolation
in cells, duplicates in source rows, and remaining missing cells separately.
Absent required core columns contribute virtual missing cells to both the
per-column counts and total remaining missing cells; the cleaned frame preserves
its input columns. Observation timestamps are UTC ISO strings (or null when no
value is observed), so reports can be serialized directly to JSON. All cleaning
counts describe the current validation invocation, not historical cumulative events.

## Consequences

Passing G2 establishes regional-series completeness. It does not certify fuel-mix
completeness or carbon-intensity accuracy. Plan 03 must explicitly account for
historical fuel reporting coverage before interpreting generation-based intensity.
No unsupported zero filling or retrospective trimming hides missing history.

The prescribed centered outlier window and linear interpolation are retrospective
cleaning. Forecast/backtest work must avoid treating future-dependent cleaning as
information available at historical issue times and document data revision limits.
