"""In-memory +30% intensity shift; isolated pre-event artifacts, no raw mutations."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from carbon_scheduler.config import get_settings
from carbon_scheduler.models.registry import read_metadata
from carbon_scheduler.models.reporting import TARGETS, load_backtest_series
from carbon_scheduler.models.training import train_region
from carbon_scheduler.monitoring import report as monitor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="CISO")
    parser.add_argument("--reuse-models", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    original, _ = load_backtest_series(args.region, TARGETS[1], settings)
    end = pd.Timestamp(original.index[-1])
    fit_end = end - pd.Timedelta(days=28)
    shift_start = end - pd.Timedelta(days=7) + pd.Timedelta(hours=1)
    isolated = settings.model_copy(
        update={"models_dir": Path(".tools/drift-simulation-models").resolve()}
    )
    if args.reuse_models:
        for target in TARGETS:
            if (
                pd.Timestamp(read_metadata(args.region, target, isolated.models_dir)["fit_end"])
                != fit_end
            ):
                raise ValueError("Simulation artifact cutoff differs from this snapshot")
    else:
        print(f"Fitting isolated simulation models through {fit_end.isoformat()}", flush=True)
        train_region(args.region, isolated, fit_end=fit_end)

    def shifted_loader(region, target, config):
        series, provenance = load_backtest_series(region, target, config)
        if target == TARGETS[1]:
            series.loc[shift_start:] *= 1.3
            provenance = {
                **provenance,
                "simulation": "Intensity +30% at/after " + shift_start.isoformat(),
                "simulation_sha256": hashlib.sha256(
                    pd.util.hash_pandas_object(series, index=True).values.tobytes()
                ).hexdigest(),
            }
        return series, provenance

    rows, reports = [], {}
    checkpoints = [
        ("before", shift_start - pd.Timedelta(hours=1)),
        *[
            (f"day_{day}", shift_start + pd.Timedelta(days=day) - pd.Timedelta(hours=1))
            for day in (1, 3, 7)
        ],
    ]
    for label, now in checkpoints:
        with patch.object(monitor, "load_backtest_series", side_effect=shifted_loader):
            report = monitor.build_monitor_report(args.region, isolated, now.to_pydatetime())
        reports[label] = json.loads(monitor.to_json(report))
        coverage = report.coverage[TARGETS[1]]
        rows.append(
            {
                "checkpoint": label,
                "n": coverage.n,
                "coverage": coverage.coverage,
                "coverage_status": coverage.status,
                "mae_ratio": report.mae_ratio[TARGETS[1]],
                "overall_status": report.status,
                "psi_target": report.feature_drift[f"{TARGETS[1]}/target"]["psi"],
            }
        )
        monitor.write_monitor_report(report, settings.reports_dir / "drift-simulation" / label)
        print(label, asdict(coverage), report.status, flush=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "drift_simulation.json").write_text(
        json.dumps(
            {
                "fit_end": fit_end.isoformat(),
                "shift_start": shift_start.isoformat(),
                "results": rows,
                "reports": reports,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    table = [
        "| Checkpoint | Realized hours | Coverage | Coverage status | "
        "MAE ratio | Target PSI | Overall |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        coverage = "N/A" if row["coverage"] is None else f"{row['coverage']:.2%}"
        ratio = "N/A" if row["mae_ratio"] is None else f"{row['mae_ratio']:.2f}"
        psi = "N/A" if row["psi_target"] is None else f"{row['psi_target']:.3f}"
        table.append(
            f"| {row['checkpoint']} | {row['n']} | {coverage} | {row['coverage_status']} | "
            f"{ratio} | {psi} | {row['overall_status']} |"
        )
    before = rows[0]
    alerted = next(
        (row["checkpoint"] for row in rows[1:] if row["coverage_status"] == "alert"), "not observed"
    )
    interpretation = (
        "Coverage was already alert before the injected shift; an incident detection "
        "delay cannot be inferred from this real-data run. "
        if before["coverage_status"] == "alert"
        else f"First sampled post-shift coverage alert: {alerted}. "
    )
    text = [
        "# Drift simulation: CISO intensity +30%",
        f"Isolated weather-free default 400-tree CQR models fit through `{fit_end.isoformat()}`; "
        f"the shift begins `{shift_start.isoformat()}`. Production pointers and raw files "
        "were not changed. The loader overlays intensity only in memory after fitting; "
        "both artifact versions, source hashes and overlay hash are in the JSON diagnostics.",
        "\n".join(table),
        interpretation + "Input PSI/KS and coverage measure different changes. Overall alerts can "
        "precede coverage alarms due to seasonality or input drift; serial dependence "
        "and overlapping reference windows make p-values operational heuristics. "
        "MAE baselines use earlier held-out CQR rows, never calibration scores. "
        "Checkpoints are sampled at days 1, 3 and 7, so delay is a bound, not an hourly estimate.",
        "A separate real tiny-model test on a stationary repeating weekly synthetic "
        "region verifies healthy pre-shift coverage and a coverage alert after seven "
        "days; this does not establish a seven-day guarantee on real deployments.",
    ]
    Path("docs/results/drift-simulation.md").write_text("\n\n".join(text) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
