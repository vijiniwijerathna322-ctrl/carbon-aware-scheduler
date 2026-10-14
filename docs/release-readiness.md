# Completion and release readiness

The implemented software, offline portfolio artifacts and measured regional
experiments are integrated into main. This record separates finished work from
acceptance that cannot be asserted from the current evidence.

## Verified

- Atomic data/model pointer writes and config-driven region propagation.
- Real CISO and ERCO ingestion, training and chronological held-out evaluation.
- Matched ERCO seasonal-naive comparisons: G3 passes both targets/all buckets.
- Both-region scheduling replay with finite matched cohorts and provenance.
- Monitoring diagnostics with strictly post-fit scoring; live CISO alert issue,
  diagnostics upload and cache preservation verified.
- Candidate drafts [6](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/pull/6)
  and [7](https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/pull/7)
  retain reviewable artifacts without automatic promotion.
- Existing reviewed CISO bundle publication, download digest/file hash checks.
- Locked key-free fresh-clone API demo, Linux/Docker CI, figures with committed
  inputs, native walkthrough, model card/datasheet, ADR index, write-up and CV notes.
- Earlier-period ERCO calibration comparison: retain 90-day defaults; 180 days
  worsened coverage. No held-out parameter tuning or promotion occurred.

## Acceptance still outstanding

CISO candidate carbon intervals miss G4 and regress on the matched cohort.
ERCO candidate demand overall coverage is 74.72%, below G4's 77% lower bound.
Neither is a qualified replacement deployment. Monitor performance support is
below 100 post-fit realized hours; input drift alerts remain open. Future
independent data must validate any frozen replacement before promotion.

ERCO has no approved deployment bundle, so its full production refresh cannot
pass prerequisites. Weekly `all` refresh preserves this explicit failure;
manual `region=CISO` exercises the existing approved selection. Automatic
candidate PR creation was denied by the repository setting; connected GitHub
created drafts without altering that setting.

No v0.2.0/v1.0.0 release or GHCR publication is claimed. The release workflow
is implemented, but the plan's live acceptance and model review are unresolved.
Do not tag a release or mark Plans 10/11 complete solely to remove pending items.
An independent five-minute reader trial, actual browser/container recording,
and repository description/topics/pinning also remain outside verified evidence.

See [regional results](results/second-region-erco.md),
[live refresh](results/live-refresh-2026-10-13.md) and
[calibration experiment](results/erco-calibration-experiment.md) for the measurements.

## Approved research release publication (2026-10-13)

The user explicitly approved v0.2.0 as a research release retaining the existing CISO demo. This supersedes the earlier no-publication status above, without waiving model production acceptance. Release run 38364497209 passed reusable CI, Docker smoke, exact-image pre-push smoke, published-digest pull smoke and latest update. GitHub research prerelease: https://github.com/vijiniwijerathna322-ctrl/carbon-aware-scheduler/releases/tag/v0.2.0.

Image: ghcr.io/vijiniwijerathna322-ctrl/carbon-aware-scheduler:0.2.0

Verified digest: sha256:3b2767ca7dbb212ba7d76f5dad4f61e08f10bb684c2bfabee01cf566174304e6

The first tag run failed ShellCheck before any registry write; its unpublished tag was corrected once to main commit 3e02388 with an exact remote lease. The successful tagged revision and image are retained. No candidate models were promoted; v1.0.0 and full production acceptance are not claimed. Anonymous package visibility remains unverified; registry smoke used the authorized runner login.

## October 14 follow-up

The actual scripted Chromium/published-container recording is complete: docs/demo/browser/research-demo.webm (65.04 seconds), real response JSON retained, artifact digest verified and extracted frames visually inspected. Monitoring refresh run 38521473770 found 46 demand and 47 carbon realized post-fit hours; current performance acceptance is still below minimum 100 and drift alerts persist (issue 9). An independent human quickstart trial and profile description/topics/pinning remain unverified; no supported repository administration/profile tool is available in this session.
