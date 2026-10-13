"""Review candidate pipelines on paired held-out forecasts, never calibration scores."""

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from carbon_scheduler.models.evaluate import summarize
from carbon_scheduler.models.reporting import TARGETS
from carbon_scheduler.regions import load_regions

KEYS = ["issue_time", "target_time", "horizon"]
VALUES = ["y", "median", "lower", "upper"]
MIN_POINTS = 100


def _flatten(values: Mapping[str, Any], prefix: str = "") -> dict[str, float | None]:
    output: dict[str, float | None] = {}
    for key, value in values.items():
        name = f"{prefix}/{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            output.update(_flatten(value, name))
        elif value is None:
            output[name] = None
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            output[name] = float(value) if math.isfinite(value) else None
        else:
            raise ValueError(f"Metric {name} must be numeric or null")
    return output


def metrics_diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> str:
    """Markdown deltas; coverage compares distance from 0.8, widths need review."""
    previous, candidate = _flatten(old), _flatten(new)
    rows = ["| Metric | Old | New | Delta | Assessment |", "|---|---:|---:|---:|---|"]
    for name in sorted(previous.keys() | candidate.keys()):
        before, after = previous.get(name), candidate.get(name)
        assessment, delta = "no comparison", "N/A"
        if before is not None and after is not None:
            delta = f"{after - before:+.4f}"
            metric = name.rsplit("/", 1)[-1]
            change = None
            if metric == "coverage":
                change = abs(after - 0.8) - abs(before - 0.8)
            elif metric in {"mae", "winkler", "pinball_lo", "pinball_hi"}:
                change = after - before
            assessment = "review"
            if change is not None:
                assessment = (
                    "unchanged"
                    if math.isclose(change, 0, abs_tol=1e-12)
                    else "regression"
                    if change > 0
                    else "improvement"
                )
        safe_name = name.replace("|", "&#124;").replace("\n", " ").replace("<", "&lt;")
        left = "N/A" if before is None else f"{before:.4f}"
        right = "N/A" if after is None else f"{after:.4f}"
        rows.append(f"| {safe_name} | {left} | {right} | {delta} | {assessment} |")
    return "\n".join(rows) + "\n"


def paired_metrics(
    old: pd.DataFrame, new: pd.DataFrame
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    """Score the same complete forecast rows with identical realized labels."""
    for frame in (old, new):
        if set(KEYS + VALUES) - set(frame):
            raise ValueError("Forecast table is missing required columns")
        if frame.duplicated(KEYS).any():
            raise ValueError("Forecast keys must be unique")
        if frame[KEYS].isna().any().any() or not frame.horizon.isin(range(1, 49)).all():
            raise ValueError("Forecast keys must be valid with horizons in 1..48")
        for column in ("issue_time", "target_time"):
            if not isinstance(frame[column].dtype, pd.DatetimeTZDtype):
                raise ValueError("Forecast timestamps must be timezone-aware")
        if not frame.target_time.equals(
            frame.issue_time + pd.to_timedelta(frame.horizon, unit="h")
        ):
            raise ValueError("Forecast target time must equal issue plus horizon")
        if ((frame.lower > frame["median"]) | (frame["median"] > frame.upper)).any():
            raise ValueError("Forecast intervals must be ordered")
    paired = old[KEYS + VALUES].merge(
        new[KEYS + VALUES], on=KEYS, suffixes=("_old", "_new"), validate="one_to_one"
    )
    columns = [f"{value}_{side}" for side in ("old", "new") for value in VALUES]
    finite = np.isfinite(paired[columns].to_numpy(dtype=float)).all(axis=1)
    equal = paired.y_old.eq(paired.y_new).to_numpy()
    counts = {
        "old_rows": len(old),
        "new_rows": len(new),
        "matched_keys": len(paired),
        "unmatched_old": len(old) - len(paired),
        "unmatched_new": len(new) - len(paired),
        "excluded_nonfinite": int((~finite).sum()),
        "different_labels": int((finite & ~equal).sum()),
        "paired_finite_rows": int((finite & equal).sum()),
    }
    if counts["paired_finite_rows"] < MIN_POINTS:
        raise ValueError("Need at least 100 paired finite rows with identical actuals")
    selected = paired.loc[finite & equal]
    summaries = []
    for side in ("old", "new"):
        frame = selected[KEYS + [f"{value}_{side}" for value in VALUES]].rename(
            columns={f"{value}_{side}": value for value in VALUES}
        )
        summaries.append(summarize(frame).replace({np.nan: None}).to_dict(orient="index"))
    return summaries[0], summaries[1], counts


def build_review(region: str, old_dir: Path | None, new_dir: Path, output: Path) -> None:
    """Generate review JSON and body from trusted raw CQR result tables."""
    load_regions()[region]
    previous, candidate, diagnostics, provenance = {}, {}, {}, {}
    for target in TARGETS:
        stem = f"backtest_{region}_{target}_cqr"
        metadata = json.loads((new_dir / f"{stem}.json").read_text(encoding="utf-8"))
        if metadata.get("data_source") != "raw" or any(
            metadata.get(key) for key in ("experiment", "exog_columns", "weather_metadata")
        ):
            raise ValueError("Candidate must use raw held-out weather-free CQR results")
        new = pd.read_parquet(new_dir / f"{stem}.parquet")
        old_path = old_dir / f"{stem}.parquet" if old_dir is not None else None
        if old_dir is not None and old_dir.exists() and not old_path.is_file():
            raise ValueError(f"Configured previous reference is missing {stem}")
        if old_path is not None and old_path.exists():
            old_metadata = json.loads(old_path.with_suffix(".json").read_text(encoding="utf-8"))
            if old_metadata.get("data_source") != "raw" or any(
                old_metadata.get(key) for key in ("experiment", "exog_columns", "weather_metadata")
            ):
                raise ValueError("Previous results must be raw held-out weather-free CQR")
            if old_metadata.get("timezone") != metadata.get("timezone"):
                raise ValueError("Evaluation timezones differ")
            if old_metadata.get("factors_sha256") != metadata.get("factors_sha256"):
                raise ValueError("Emission factor definitions differ")
            previous[target], candidate[target], diagnostics[target] = paired_metrics(
                pd.read_parquet(old_path), new
            )
            provenance[target] = {"old": old_metadata, "new": metadata}
        else:
            _, candidate[target], diagnostics[target] = paired_metrics(new, new)
            diagnostics[target]["previous_missing"] = True
            provenance[target] = {"old": None, "new": metadata}
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "region": region,
        "old": previous,
        "new": candidate,
        "counts": diagnostics,
        "provenance": provenance,
    }
    (output / "metrics.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    body = (
        f"Candidate retraining for {region}. Human review is required.\n\n"
        "Metrics evaluate chronological rolling-origin pipeline refits, not the latest "
        "artifact fitted through the end of history. Calibration scores are not held-out evidence. "
        "Rows are paired by issue, target and horizon with identical actuals; excluded "
        "or revised labels are counted. Coverage assessment uses distance from nominal 80%; "
        "Interval width changes require review. These deltas are descriptive, "
        "not significance tests.\n\n"
        + metrics_diff(previous, candidate)
        + "\nPairing counts:\n\n```json\n"
        + json.dumps(diagnostics, indent=2)
        + "\n```\n\n"
        + "Candidate demo and metrics are versioned under candidates/. Merging this PR "
        "does not change deployed model pointers or refresh deployment variables. "
        "Review regressions, cohort exclusions and source provenance "
        "before separately promoting artifacts.\n"
    )
    (output / "review.md").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--old-dir", type=Path)
    parser.add_argument("--new-dir", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_review(args.region, args.old_dir, args.new_dir, args.output)
