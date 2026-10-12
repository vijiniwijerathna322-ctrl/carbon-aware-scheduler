"""Offline scheduling report with source and skipped-cohort diagnostics."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from carbon_scheduler.config import Settings
from carbon_scheduler.models.reporting import _table, load_backtest_series
from carbon_scheduler.scheduler.replay import make_jobs, replay_scheduling, summarize_replay


def run_schedule_backtest(
    region: str, settings: Settings, reports_dir: Path = Path("reports")
) -> Path:
    actual, provenance = load_backtest_series(region, "carbon_intensity_g_per_kwh", settings)
    source = reports_dir / f"backtest_{region}_carbon_intensity_g_per_kwh_cqr.parquet"
    metadata = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
    for key in ("data_source", "input_sha256", "factors_sha256"):
        if metadata.get(key) != provenance.get(key):
            raise ValueError(f"Forecast and actual provenance disagree: {key}; rerun backtest")
    forecasts = pd.read_parquet(source)
    start, end = pd.Timestamp(metadata["test_start"]), pd.Timestamp(metadata["test_end"])
    if not ((forecasts.issue_time >= start) & (forecasts.issue_time <= end)).all():
        raise ValueError("Forecast issue times are outside the recorded test interval")
    # Never score future observations beyond the original held-out interval.
    actual = actual.loc[start:end]
    issues = pd.DatetimeIndex(forecasts.issue_time.drop_duplicates().sort_values())
    jobs = make_jobs(issues)
    results = [
        replay_scheduling(actual, forecasts, jobs, strategy) for strategy in ("median", "upper")
    ]
    if not results[0].status.equals(results[1].status):
        raise ValueError("Strategies have different scoring cohorts")
    if not (results[0].status == "scored").any():
        raise ValueError("No jobs could be scored; check actual coverage and forecast validity")
    parts = [
        f"# {region} scheduling replay",
        f"Test interval: {start.isoformat()} through {end.isoformat()} (inclusive UTC).",
        "Illustrative constant-power 7 kW EV jobs: durations 1, 2, 4, 8 hours; "
        "deadline windows 6, 12, 24, 36 hours. Arrival is the daily forecast issue time. "
        "These overlapping scenarios are equally weighted, not a measured fleet workload.",
        "The issue-hour observation supplies h=0 under zero observation latency; "
        "h=1 onward uses CQR forecasts only. Actual future values only score outcomes "
        "and the hindsight oracle. Complete actual coverage of every feasible hour "
        "is required, preventing oracle comparisons on unequal support.",
        "Savings are percentages: 100 × (baseline − chosen) / baseline. Zero baselines "
        "use zero by convention. Negative lower bounds are clipped to physical zero. "
        "Upper is an uncertainty heuristic: carbon G4 failed and summed pointwise "
        "bounds are not a calibrated job-level confidence interval.",
    ]
    comparison = pd.DataFrame(
        [summarize_replay(result).loc["all"] for result in results],
        index=["median", "upper"],
    )
    parts.extend(["## Strategy comparison", _table(comparison)])
    for strategy, result in zip(("median", "upper"), results, strict=True):
        summary = summarize_replay(result)
        parts.extend(
            [
                f"## {strategy}",
                f"Scored {int((result.status == 'scored').sum())} / {len(result)} jobs.",
                _table(summary),
                "Skipped reasons: "
                + json.dumps(
                    result.loc[result.status == "skipped", "reason"].value_counts().to_dict()
                ),
            ]
        )
    median_mean = float(summarize_replay(results[0])["mean_savings_pct"].loc["all"])
    parts.append(f"G5: {'PASS' if median_mean > 0 else 'FAIL'} (median mean realized savings > 0).")
    parts.extend(
        [
            "## Provenance",
            "```json\n"
            + json.dumps(
                {
                    **provenance,
                    "forecast_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "forecast_metadata": metadata,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n```",
        ]
    )
    path = reports_dir / f"schedule_backtest_{region}.md"
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    pd.concat(results, ignore_index=True).to_parquet(path.with_suffix(".parquet"), index=False)
    return path
