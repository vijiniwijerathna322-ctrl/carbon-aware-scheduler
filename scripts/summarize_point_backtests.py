"""Publish paired G3 results and hour/month diagnostics from saved backtests."""

import hashlib
import json
import platform
import re
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_scheduler.models.evaluate import compare_point_forecasts, summarize
from carbon_scheduler.models.lgbm import DEFAULT_PARAMS
from carbon_scheduler.models.reporting import TARGETS, render_backtest_report

ROOT = Path(__file__).resolve().parents[1]


def table(frame: pd.DataFrame) -> str:
    lines = [
        "| " + " | ".join(["bucket", *frame.columns]) + " |",
        "|" + "---|" * (len(frame.columns) + 1),
    ]
    for name, row in frame.iterrows():
        values = []
        for column, value in row.items():
            if pd.isna(value):
                values.append("N/A")
            elif column == "g3_pass":
                values.append("PASS" if value else "FAIL")
            elif column == "n":
                values.append(str(int(value)))
            else:
                values.append(f"{value:.6f}")
        lines.append("| " + " | ".join([str(name), *values]) + " |")
    return "\n".join(lines)


def main() -> None:
    ranges = []
    for target in TARGETS:
        for model in ("naive", "lgbm"):
            report = ROOT / "reports" / f"backtest_CISO_{target}_{model}.md"
            match = re.search(
                r"Test interval \(UTC\): (\S+) to (\S+)\.", report.read_text(encoding="utf-8")
            )
            if match is None:
                raise ValueError(f"No test interval recorded in {report}")
            ranges.append(match.groups())
    if len(set(ranges)) != 1:
        raise ValueError("All model runs must use the same test interval")
    start, end = ranges[0]
    sections = [
        "# CISO point-forecast backtest",
        "",
        f"Test data: {start} through {end} (UTC). "
        "Daily America/Los_Angeles midnight issues, horizons 1–48, "
        "30-local-calendar-day refits. Each refit uses all earlier history. "
        "Training issues occur every three UTC hours. Defaults are unchanged "
        "from Plan 04; no tuning on this test period.",
        "",
        "Raw observations are used pointwise without retrospective interpolation "
        "or centered cleaning. Demand <= 0 is masked; missing values are retained. "
        "This is a latest-revision simulation assuming zero reporting latency, "
        "not an as-published historical replay. Carbon describes the covered "
        "observed-generation lifecycle proxy, excluding OTH/storage and imports. "
        "Partial fuel data remains a limitation. See ADRs 0001, 0002, 0003 and 0005.",
        "",
        "G3 compares paired finite predictions and identical labels. Full-model "
        "summaries below disclose differing availability. n_interval may differ "
        "from point n. Raw quantile coverage is uncalibrated, not a Plan 05 verdict.",
        "",
    ]
    verdicts = []
    for target in TARGETS:
        predictions = {}
        summaries = {}
        for model in ("naive", "lgbm"):
            path = ROOT / "reports" / f"backtest_CISO_{target}_{model}.parquet"
            predictions[model] = pd.read_parquet(path)
            summaries[model] = summarize(predictions[model])
            summaries[model].attrs.update(test_start=start, test_end=end)
        comparison = compare_point_forecasts(predictions["naive"], predictions["lgbm"])
        verdicts.append(bool(comparison.loc[["1-6", "7-24", "25-48"], "g3_pass"].all()))
        sections.extend([f"## Paired comparison: {target}", "", table(comparison), ""])
        for model in ("naive", "lgbm"):
            sections.extend([render_backtest_report({model: summaries[model]}, "CISO", target), ""])
        merged = predictions["naive"].merge(
            predictions["lgbm"],
            on=["issue_time", "target_time", "horizon"],
            suffixes=("_naive", "_lgbm"),
            validate="one_to_one",
        )
        finite = np.isfinite(merged[["y_naive", "median_naive", "median_lgbm"]]).all(axis=1)
        merged = merged.loc[finite].copy()
        local = merged.target_time.dt.tz_convert("America/Los_Angeles")
        merged["hour_local"] = local.dt.hour
        merged["month_local"] = local.dt.month
        for model in ("naive", "lgbm"):
            merged[f"error_{model}"] = (merged.y_naive - merged[f"median_{model}"]).abs()
        for group in ("hour_local", "month_local"):
            diagnostic = merged.groupby(group).agg(
                n=("y_naive", "size"),
                mae_naive=("error_naive", "mean"),
                mae_lgbm=("error_lgbm", "mean"),
            )
            sections.extend([f"### {target}: {group}", "", table(diagnostic), ""])
    sections.extend(
        [
            f"## Gate G3: {'PASS' if all(verdicts) else 'FAIL'}",
            "",
            "LightGBM must improve paired MAE in every horizon bucket for both targets. "
            "Individual monthly/hourly differences are diagnostics, not tuning criteria.",
            "",
            "## Reproducibility",
            "",
            f"- Python: {platform.python_version()}",
            *[
                f"- {package}: {version(package)}"
                for package in ("lightgbm", "numpy", "pandas", "scikit-learn")
            ],
        ]
    )
    sections.append(
        "- LightGBM defaults: `"
        + json.dumps({**DEFAULT_PARAMS, "seed": 42, "n_jobs": 1, "issue_step_h": 3}, sort_keys=True)
        + "`"
    )
    for name, path in {
        "raw input": ROOT / "data/raw/CISO/hourly.parquet",
        "emission factors": ROOT / "config/emission_factors.yaml",
        "dependency lock": ROOT / "uv.lock",
        "feature implementation": ROOT / "src/carbon_scheduler/features/build.py",
        "model implementation": ROOT / "src/carbon_scheduler/models/lgbm.py",
    }.items():
        sections.append(f"- {name} SHA-256: {hashlib.sha256(path.read_bytes()).hexdigest()}")
    for path in sorted((ROOT / "reports").glob("backtest_CISO_*.parquet")):
        sections.append(f"- {path.name} SHA-256: {hashlib.sha256(path.read_bytes()).hexdigest()}")
    directory = ROOT / "docs/results"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "backtest-point.md"
    path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(f"G3 {'PASS' if all(verdicts) else 'FAIL'}; results: {path}")


if __name__ == "__main__":
    main()
