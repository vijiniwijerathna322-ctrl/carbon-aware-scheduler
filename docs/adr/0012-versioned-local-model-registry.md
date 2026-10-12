# ADR 0012: Versioned local model artifacts

## Context

Decision D6 calls for local file storage. Model artifacts need metadata, stable
current-version selection, reproducible reloads and a clear compatibility check.

## Decision

Store each artifact at models/{region}/{target}/{UTC-timestamp}-{random-suffix}/
with model.joblib and metadata.json. A unique suffix prevents two saves within
one second from overwriting an earlier version. Write the complete version into
a temporary directory, then atomically rename it and replace current.json last.
Old versions remain available. A failure updating the pointer may leave a valid
unselected version, which can still be loaded explicitly.

Metadata records model splits/features/corrections, provenance, descriptive
calibration metrics, UTC trained_at, package versions, git SHA and pickle digest.
Nonfinite descriptive metrics become JSON null rather than invalid JSON NaN.
Loading checks paths remain within the configured registry, safe identifiers,
feature order, package compatibility and digest before deserializing. Python
major/minor must match; LightGBM, pandas, numpy and joblib versions must match
exactly. Missing/deleted pointers give a train-command remediation hint.

## Consequences

Joblib is a trusted-local serialization format, not an interchange format for
untrusted downloads. The digest detects corruption, not malicious modifications
by someone with write access to the trusted registry. Training verifies identical
predictions after reload. Explicit version loads avoid current-pointer changes
between selecting metadata and loading the corresponding model.
