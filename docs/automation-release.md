# Container releases and dependency updates

The release workflow accepts stable tags of the form `vMAJOR.MINOR.PATCH`. The tagged commit must already be an ancestor of `main`. It invokes the same reusable CI workflow at the tagged revision, including workflow validation, lint, types, coverage and Docker smoke. A failed gate prevents the registry job from running. Only the publish job receives packages write permission; no EIA secret is used.

The publish job builds and loads one Linux amd64 image with source/revision/version labels, runs the existing-image smoke test, logs in with the workflow token and pushes that tested version to `ghcr.io/<owner>/carbon-aware-scheduler:<version>`. It resolves the registry digest, pulls that digest and runs the offline non-root/read-only assertions again. Only then does it push `latest`. The verified digest is recorded in the Actions summary. This sequence follows the official [GitHub container publishing contract](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).

Registry verification failure can leave a version tag already published, but it prevents updating `latest`. `latest` means the last successfully completed release, not necessarily the greatest semantic version if tags are released out of order. Existing published version tags are rejected before pushing; a run that published a version before failing verification requires review and a new release version rather than automatic overwrite. Consumers needing immutable artifacts should pin the recorded digest. Publication visibility is controlled by GHCR package settings; an initial package may need to be made public for anonymous pulls.

## Smoke modes

```bash
# Build the local checkout and test it (default CI behavior).
bash scripts/smoke_docker.sh

# Verify a prebuilt image without rebuilding it.
IMAGE=carbon-scheduler:smoke SMOKE_MODE=local bash scripts/smoke_docker.sh

# Pull and verify a published version or digest.
IMAGE=ghcr.io/<owner>/carbon-aware-scheduler:0.2.0 SMOKE_MODE=pull bash scripts/smoke_docker.sh
```

The script checks health, six-hour forecasts, explicit monitoring-report absence, a scheduling recommendation and non-root execution under read-only filesystem/capability restrictions. CI exercises build and local modes. Pull mode is used by the tag-triggered release job.

## Dependency hygiene

Dependabot runs weekly on Monday at 06:00 UTC for the native `uv` ecosystem and GitHub Actions. GitHub now documents [native uv support](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories), so this replaces the original plan's generic pip entry. Both update streams allow at most five open PRs. Updates are reviewed through normal CI. Model artifacts require compatible pinned numeric-library versions, so a dependency update may also require fresh artifacts or an explicit decision to retain the lockfile version; the offline demo validation catches incompatibility.

## Publication status

Release workflow code, dependency config and smoke modes are integrated through the Plan 10 bootstrap exception. `v0.2.0` has not been created or pushed and no GHCR image publication is claimed. Plan 10 still has pending ERCO live evaluation, refresh deployment bundles/live dispatch and actual retrain PR review. ADR 0018 permits verified workflow code to merge before live acceptance so main-only workflows can run. Plan 10 remains in progress after that bootstrap integration. Complete the live prerequisites before publishing the version tag and inspecting its digest smoke result.
