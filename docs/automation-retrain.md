# Retraining candidates for human review

The retrain workflow is manual-only and runs from `main`. Select a configured region. It ingests current history, builds the dataset, trains default raw-target CQR artifacts, runs six-month chronological backtests for both targets, builds an independently verified offline demo, runs the quality gate and opens a draft PR. EIA failures stop the pipeline before a PR is opened. No auto-merge or deployment-variable update is included.

## Inputs and review outputs

Configure the `EIA_API_KEY` Actions secret. Optionally set `<REGION>_MODELS_RUN_ID` to the previously reviewed deployment bundle described in refresh operations. Previous references must come from successful non-PR runs on `main` in this repository. If none is configured, the first candidate's table explicitly shows no comparison. A configured but incomplete reference fails rather than silently dropping target results.

Candidates are stored at `candidates/<REGION>/<run-id>-<attempt>/demo/`, with JSON metrics and a Markdown review under `evaluation/`. This keeps the shipped demo and production pointers separate from unreviewed candidates. The draft PR commits only that candidate directory. Its branch includes region, run and attempt identifiers to prevent same-day collisions. Full prediction tables and quality reports are retained as Actions artifacts for 30 days under `retrain-candidate-*`, deliberately distinct from approved `monitoring-models-*` artifacts.

The comparison aligns old and new forecasts on issue time, target time and horizon. It keeps only finite actuals and intervals on both sides with exactly equal labels, counts unmatched/revised/missing rows and requires at least 100 usable paired forecasts. Duplicate keys, invalid interval order, invalid timestamps, different factor definitions or weather-experiment references are rejected. This avoids presenting changes in evaluation samples as pure model improvements. Horizon buckets with no usable rows remain unavailable. Wider or narrower intervals require interpretation; coverage assessment uses distance from nominal 80%. MAE, pinball and Winkler increases are marked as regressions. Flags are descriptive and do not replace the project's fixed coverage gates.

Metrics describe rolling-origin pipeline refits. They do not certify a candidate artifact trained through the latest observation against that earlier held-out window. Calibration scores are not used for this diff. Review the complete source provenance and excluded counts before accepting a candidate.

## PR permissions and promotion

Repository settings must allow GitHub Actions to create pull requests. The job requests only contents write, pull-requests write and actions read. The action uses `GITHUB_TOKEN`. GitHub generally suppresses downstream workflows triggered by that token, so this workflow runs the quality gate itself before opening the draft. A reviewer should run or confirm required candidate checks before merging. See the official [create-pull-request permission contract](https://github.com/peter-evans/create-pull-request) and [GITHUB_TOKEN behavior](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).

Merging the draft retains the reviewed candidate; it does not deploy it. Separate promotion must preserve exact artifact hashes, establish the selected pointers, retain matched held-out baseline files and publish a reviewed `monitoring-models-<REGION>` bundle before updating refresh variables. That deployment publishing path is not implemented by this task. Candidate byte hashes are protected by `.gitattributes` across Windows/Linux checkouts.

## Validation status

Unit tests cover regression flags, unavailable previous values, coverage distance, pairing exclusions, duplicate/minimum-sample rejection, strict JSON review artifacts and rejection of weather results. Workflow YAML, embedded Python and actionlint are checked. A local review-format preview reuses the existing CISO held-out reports on both sides, so it is a formatting/provenance verification with zero deltas, not a new retraining experiment.

Live dispatch and inspection of an actual generated PR remain pending the Actions secret/settings and availability of upstream EIA data. The workflow code is integrated through the ADR 0018 bootstrap exception; no successful production run is claimed.

## Committed validation requests

A newly added JSON file under `.github/validation-requests/` on main can request the existing manual retrain workflow for explicitly listed CISO/ERCO regions. The dispatcher only accepts new files and the retrain-candidate operation, with actions write permission scoped to its job. It never reads or exports the EIA secret, promotes models, merges PRs or dispatches arbitrary workflows. This bridge is used when the connected repository tools cannot dispatch workflows directly. GitHub documents workflow_dispatch as an exception to token-trigger suppression. The 2026-10-13 request records the user-confirmed secret/settings and preserves human review.
