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
