"""Publish held-out CQR coverage and preserve misses without test-period tuning."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from carbon_scheduler.models.evaluate import compare_point_forecasts, coverage_verdict, summarize
from carbon_scheduler.models.reporting import TARGETS, render_backtest_report
from carbon_scheduler.models.reporting import _table as table

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sections = [
        "# CISO held-out CQR interval backtest",
        "",
        "Daily local-midnight issues, horizons 1–48, refits every 30 local calendar "
        "days. Each fit reserves its final 90 days for calibration and trains only "
        "on targets at or before calibration_start. Calibration issues are strictly "
        "later than that boundary; calibration targets never exceed fit_end. "
        "Only realized labels in the six test months contribute to tables below.",
        "",
        "Nominal coverage is 80%. G4 requires overall coverage within 77–83% and "
        "at least 70% in every horizon bucket. Defaults were fixed before seeing "
        "these test results. No test-period feature, parameter or calibration "
        "window tuning was performed. Reused training-time calibration summaries "
        "are excluded from held-out coverage claims.",
        "",
        "Inputs follow ADR 0005: pointwise raw demand and carbon proxy, without "
        "retrospective cleaning. Latest revisions and zero observation latency are "
        "assumed. Partial fuel mixes, excluded OTH/storage and ignored imports "
        "remain limitations. CQR's exchangeability assumption does not remove "
        "time-series dependence or distribution drift (ADR 0004).",
        "",
    ]
    verdicts = []
    for target in TARGETS:
        stem = ROOT / "reports" / f"backtest_CISO_{target}_cqr"
        pred = pd.read_parquet(stem.with_suffix(".parquet"))
        metadata = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
        summary = summarize(pred)
        summary.attrs.update(metadata)
        verdict = coverage_verdict(summary)
        verdicts.append(verdict)
        sections.extend(
            [
                render_backtest_report(
                    {"cqr": summary}, "CISO", target, predictions_by_model={"cqr": pred}
                ),
                "",
            ]
        )
        naive = pd.read_parquet(ROOT / "reports" / f"backtest_CISO_{target}_naive.parquet")
        comparison = compare_point_forecasts(naive, pred)
        sections.extend(
            [f"## Paired CQR median versus weekly baseline: {target}", "", table(comparison), ""]
        )
        sections.append(
            f"- {stem.name}.parquet SHA-256: "
            + hashlib.sha256(stem.with_suffix(".parquet").read_bytes()).hexdigest()
        )
    sections.extend(["", f"## Combined G4: {'PASS' if all(verdicts) else 'FAIL'}", ""])
    if not all(verdicts):
        sections.extend(
            [
                "The target is missed and is retained as a measured limitation. "
                "Coverage varies by local hour and month in the tables above. "
                "This fixed 90-day bucket calibration does not certify nominal "
                "held-out coverage under temporal drift. Future calibration changes "
                "must be selected on a pre-test chronological validation window and "
                "evaluated on fresh held-out data; these test results must remain visible.",
                "",
            ]
        )
    sections.extend(["## Reproducibility", ""])
    sections.extend(
        f"- {name}: {version(name)}" for name in ("lightgbm", "pandas", "numpy", "joblib")
    )
    for name in ("conformal.py", "forecast_model.py"):
        sections.append(
            f"- {name} SHA-256: "
            + hashlib.sha256((ROOT / "src/carbon_scheduler/models" / name).read_bytes()).hexdigest()
        )
    path = ROOT / "docs/results/backtest-cqr.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(f"G4 {'PASS' if all(verdicts) else 'FAIL'}; held-out results: {path}")


if __name__ == "__main__":
    main()
