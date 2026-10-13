# ADR 0018: Integrate automation before live validation

## Context

Plan 10's one-branch agreement previously required all live checks before merging. Scheduled workflows require the default branch, while retraining and release source guards require main. Deployment bundles also require reviewed successful main runs. Those requirements create a circular dependency. EIA DNS currently fails locally and authenticated GitHub access is not connected.

## Decision

Merge the locally and Linux-CI verified automation implementation into main before running its live acceptance checks. Retain Plan 10's in-progress status and all pending live checkboxes. This integration does not declare successful ERCO evaluation, deployment, retraining review or a completed release. Do not create v0.2.0 until its remaining validations pass.

Prepare local deployment bundles from explicitly selected validated models and configuration-matched held-out baselines. The allowlist excludes secrets, raw histories and existing monitor reports. The manifest records exact file hashes and pending review; preparing a bundle does not publish or approve it. GitHub plugin connection and repository secrets/settings are required before authenticated workflow operations.

## Consequences

Default-branch workflows can be discovered and dispatched once prerequisites exist. Scheduled refresh may fail visibly until repository configuration and reviewed artifacts are provided. The source-review and model-promotion boundaries remain explicit. Main contains tested workflow code while the master plan truthfully records incomplete live acceptance. An external connectivity failure cannot be reported as successful model generalisation.
