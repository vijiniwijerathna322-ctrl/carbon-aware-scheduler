# D6: Atomic Parquet hourly storage

## Context

Ingestion needs typed, UTC hourly datasets that can be reused without querying EIA.
Incremental refreshes must preserve history and accept revised values, including nulls.

## Decision

Store raw observations and cleaned interim output separately under
`data/<stage>/<region>/hourly.parquet`, using pandas and PyArrow. Require a regular,
increasing nanosecond UTC index named `period`. Write a temporary sibling file and
atomically replace the destination; skip replacement when the frame equals the cache.
Validate region codes against the metadata registry before constructing paths.

Refresh the last 48 hours inclusively. Explicit older starts backfill history; historical
end bounds preserve later cached data. New hourly rows win, including missing values.
Retain the union of observed fuel columns and leave absent fuel observations missing.
Represent every requested boundary hour in quality metrics, even for empty responses.

## Consequences

Parquet preserves types and UTC timestamps; equal reruns preserve file bytes. There is
no multi-writer locking, so callers must serialize ingestion for a region. The persisted
quality JSON describes the last data-changing fetch and merged dataset. An unchanged
rerun leaves that provenance intact; its returned report counts duplicates in that
current fetch. G2 covers all four core series and does not certify fuel completeness.

Processed storage is reserved for the carbon-intensity stage. Ingestion extends the
store stage contract with `raw`, so repeated cleaning always starts from observations.
Legacy interim-only caches are accepted as a migration fallback until raw is written.

Live full-history requests showed repeated slow deep-offset pages (some exceeding
30 seconds); a bounded annual query returned promptly. Partition API requests into
adjacent calendar-year UTC windows. Each window ends at December 31 23:00, and
the next starts January 1 00:00; inclusive EIA bounds therefore do not duplicate
boundary hours. Aggregate both routes before merging and cleaning, preserving
full requested history and unchanged G2 coverage. Single-year intervals stay intact.

After both routes complete a calendar-year window, atomically checkpoint its
merged raw observations, including missing boundary hours. A failed route does
not persist a half-fetched year. A retry refreshes the last 48 hours of completed
raw history and continues forward. Cleaned interim data and its quality report
are updated only after every requested window succeeds; failed runs do not claim
G2 completion. Existing interim output remains available but may lag raw checkpoints.

Historical backfills starting before the existing cache minimum defer all raw
checkpoint writes until every requested window succeeds. A failure therefore
preserves the original raw bytes and minimum timestamp, ensuring a retry still
fetches the unfinished older prefix. Initial downloads and forward refreshes
retain annual checkpoint/resume behavior.
