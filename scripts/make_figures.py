"""Regenerate portfolio figures from saved raw CISO evaluation outputs."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from carbon_scheduler.models.evaluate import coverage_table, summarize  # noqa: E402
from carbon_scheduler.models.reporting import TARGETS  # noqa: E402

COLORS = ["#0072B2", "#D55E00", "#009E73"]


def coverage_figure(predictions):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for target, color in zip(TARGETS, COLORS, strict=False):
        for axis, grouping in zip(axes, ["horizon_bucket", "hour_local"], strict=True):
            table = coverage_table(predictions[target], grouping, "America/Los_Angeles")
            if grouping == "horizon_bucket":
                table = table.iloc[:-1]
            axis.plot(
                table.index.astype(str),
                table.coverage * 100,
                "o-",
                color=color,
                label="Demand" if target == TARGETS[0] else "Carbon",
            )
    for axis in axes:
        axis.axhline(80, color="#333333", linestyle="--", label="Nominal 80%")
        axis.set_ylim(0, 100)
        axis.set_ylabel("Realized coverage (%)")
        axis.legend(fontsize=8)
    axes[0].set_xlabel("Forecast horizon (hours)")
    axes[1].set_xlabel("Target hour (America/Los_Angeles)")
    axes[1].set_xticks(range(0, 24, 3))
    fig.suptitle("Carbon coverage misses its gate; overall averages hide hourly gaps")
    return fig


def fan_figure(predictions):
    frame = (
        predictions[TARGETS[1]]
        .sort_values("issue_time")
        .drop_duplicates("target_time", keep="last")
    )
    frame = frame.sort_values("target_time")
    week = frame.loc[frame.target_time < frame.target_time.min() + pd.Timedelta(days=7)]
    fig, axis = plt.subplots(figsize=(12, 4), layout="constrained")
    axis.fill_between(
        week.target_time,
        week.lower,
        week.upper,
        color=COLORS[0],
        alpha=0.2,
        label="Nominal 80% band (coverage gate missed)",
    )
    axis.plot(week.target_time, week["median"], color=COLORS[0], label="Forecast median")
    axis.plot(week.target_time, week.y, color=COLORS[1], label="Actual proxy")
    axis.set(
        xlabel="Realized target time (UTC)",
        ylabel="Carbon proxy (gCO2e/kWh)",
        title="One held-out week: uncertainty varies with the generation mix",
    )
    axis.legend(fontsize=8)
    return fig


def mae_figure(predictions, naive):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for axis, target in zip(axes, TARGETS, strict=True):
        left, right = (
            naive[target].set_index(["issue_time", "target_time", "horizon"]),
            predictions[target].set_index(["issue_time", "target_time", "horizon"]),
        )
        keys = left.index.intersection(right.index)
        valid = np.isfinite(left.loc[keys, ["y", "median"]]).all(axis=1) & np.isfinite(
            right.loc[keys, ["y", "median"]]
        ).all(axis=1)
        valid &= left.loc[keys, "y"].eq(right.loc[keys, "y"])
        keys = keys[valid]
        for data, label, color in [
            (left, "Seasonal naive", COLORS[1]),
            (right, "CQR median", COLORS[0]),
        ]:
            table = summarize(data.loc[keys].reset_index()).iloc[:-1]
            axis.plot(table.index, table.mae, "o-", label=label, color=color)
        axis.set(
            xlabel="Forecast horizon (hours)",
            ylabel="MAE (MWh)" if target == TARGETS[0] else "MAE (gCO2e/kWh)",
        )
        axis.legend()
        axis.set_ylim(bottom=0)
    fig.suptitle("CQR medians improve over weekly persistence on matched forecast rows")
    return fig


def savings_figure(frame):
    fig, axis = plt.subplots(figsize=(9, 4), layout="constrained")
    for strategy, color in zip(["median", "upper"], COLORS, strict=False):
        scored = frame.loc[(frame.strategy == strategy) & (frame.status == "scored")]
        table = scored.groupby("window_h")[["savings_pct", "oracle_savings_pct"]].mean()
        axis.plot(table.index, table.savings_pct, "o-", color=color, label=strategy)
        if strategy == "median":
            axis.plot(
                table.index,
                table.oracle_savings_pct,
                "s--",
                color=COLORS[2],
                label="Hindsight oracle",
            )
    axis.set(
        xlabel="Deadline window (hours)",
        ylabel="Mean scenario savings vs run-now (%)",
        title="Longer deadlines offer flexibility; both strategies trail the oracle",
    )
    axis.legend()
    return fig


def drift_figure(rows):
    fig, axis = plt.subplots(figsize=(9, 4), layout="constrained")
    axis.plot([0, 1, 3, 7], [row["coverage"] * 100 for row in rows], "o-", color=COLORS[1])
    axis.axhline(80, linestyle="--", color="#333333", label="Nominal 80%")
    axis.set(
        xlabel="Sampled days after +30% intensity shift (0 = before)",
        ylabel="Realized carbon coverage (%)",
        ylim=(50, 100),
        title="Coverage alarm appears at day 7; input alarms existed before the shift",
    )
    axis.legend()
    return fig


def make_figures(reports_dir: Path, out_dir: Path) -> list[Path]:
    required = [
        reports_dir / f"backtest_CISO_{target}_{model}.parquet"
        for target in TARGETS
        for model in ("cqr", "naive")
    ]
    required += [
        reports_dir / "schedule_backtest_CISO.parquet",
        reports_dir / "drift_simulation.json",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(
                f"Missing {path}; run raw backtests, schedule-backtest and simulate_drift first"
            )
    predictions = {target: pd.read_parquet(required[i * 2]) for i, target in enumerate(TARGETS)}
    naive = {target: pd.read_parquet(required[i * 2 + 1]) for i, target in enumerate(TARGETS)}
    out_dir.mkdir(parents=True, exist_ok=True)
    figures = [
        fan_figure(predictions),
        coverage_figure(predictions),
        mae_figure(predictions, naive),
        savings_figure(pd.read_parquet(required[-2])),
        drift_figure(json.loads(required[-1].read_text())["results"]),
    ]
    paths = []
    for name, fig in zip(
        ["forecast-fan", "coverage", "mae", "savings", "drift"], figures, strict=True
    ):
        path = out_dir / f"{name}.png"
        fig.savefig(path, dpi=160, facecolor="white")
        plt.close(fig)
        paths.append(path)
    (out_dir / "provenance.json").write_text(
        json.dumps(
            {str(path.name): hashlib.sha256(path.read_bytes()).hexdigest() for path in required},
            indent=2,
        )
        + "\n"
    )
    schedules = pd.read_parquet(required[-2])
    summary = {
        "scope": "CISO raw held-out forecasts and illustrative scenario replay",
        "targets": {
            target: summarize(frame).to_dict(orient="index")
            for target, frame in predictions.items()
        },
        "scheduling": schedules.loc[schedules.status == "scored"]
        .groupby("strategy")
        .agg(
            n=("savings_pct", "size"),
            mean_savings_pct=("savings_pct", "mean"),
            oracle_savings_pct=("oracle_savings_pct", "mean"),
        )
        .to_dict(orient="index"),
    }
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--out-dir", type=Path, default=Path("docs/figures"))
    args = parser.parse_args()
    make_figures(args.reports_dir, args.out_dir)
    summary_path = Path("docs/results/portfolio-summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_bytes((args.out_dir / "metrics.json").read_bytes())
