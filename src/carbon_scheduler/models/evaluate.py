"""Horizon-bucket summaries with explicit point and interval sample counts."""

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd

from carbon_scheduler.models.metrics import (
    interval_coverage,
    mae,
    mean_interval_width,
    pinball_loss,
    winkler_score,
)

BUCKETS = ((1, 6), (7, 24), (25, 48))


def summarize(
    pred: pd.DataFrame,
    alpha: float = 0.2,
    buckets: Sequence[tuple[int, int]] = BUCKETS,
) -> pd.DataFrame:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    groups = [(f"{lo}-{hi}", pred.loc[pred.horizon.between(lo, hi)]) for lo, hi in buckets]
    groups.append(("all", pred))
    rows = []
    for label, frame in groups:
        point_valid = np.isfinite(frame[["y", "median"]].to_numpy(dtype=float)).all(axis=1)
        interval_valid = np.isfinite(frame[["y", "lower", "upper"]].to_numpy(dtype=float)).all(
            axis=1
        )
        # Width uses the same realized-label sample as interval coverage.
        interval = frame.loc[interval_valid]
        rows.append(
            {
                "bucket": label,
                "n": int(point_valid.sum()),
                "n_interval": int(interval_valid.sum()),
                "mae": mae(frame.y, frame["median"]),
                "coverage": interval_coverage(frame.y, frame.lower, frame.upper),
                "mean_width": mean_interval_width(interval.lower, interval.upper),
                "pinball_lo": pinball_loss(frame.y, frame.lower, alpha / 2),
                "pinball_hi": pinball_loss(frame.y, frame.upper, 1 - alpha / 2),
                "winkler": winkler_score(frame.y, frame.lower, frame.upper, alpha),
            }
        )
    return pd.DataFrame(rows).set_index("bucket")


def coverage_table(
    pred: pd.DataFrame,
    by: Literal["horizon_bucket", "hour_local", "month_local"],
    tz: str,
    alpha: float = 0.2,
) -> pd.DataFrame:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    groups: list[tuple[str | int, pd.DataFrame]]
    if by == "horizon_bucket":
        groups = [(f"{lo}-{hi}", pred.loc[pred.horizon.between(lo, hi)]) for lo, hi in BUCKETS]
        groups.append(("all", pred))
    elif by in ("hour_local", "month_local"):
        local = pred.target_time.dt.tz_convert(tz)
        values = local.dt.hour if by == "hour_local" else local.dt.month
        labels = range(24) if by == "hour_local" else range(1, 13)
        groups = [(label, pred.loc[values == label]) for label in labels]
    else:
        raise ValueError("Unknown coverage grouping")
    rows = []
    for label, frame in groups:
        valid = np.isfinite(frame[["y", "lower", "upper"]].to_numpy(dtype=float)).all(axis=1)
        observed = frame.loc[valid]
        rows.append(
            {
                "group": label,
                "n": len(observed),
                "coverage": interval_coverage(observed.y, observed.lower, observed.upper),
                "mean_width": mean_interval_width(observed.lower, observed.upper),
            }
        )
    return pd.DataFrame(rows).set_index("group")


def coverage_verdict(summary: pd.DataFrame) -> bool:
    """Fixed 80% G4 target: overall 77–83%, every bucket at least 70%."""
    buckets = summary.loc[[f"{lo}-{hi}" for lo, hi in BUCKETS]]
    overall = summary.loc[["all"], "coverage"].to_numpy(dtype=float)[0]
    return bool(
        0.77 <= overall <= 0.83  # noqa: PLR2004
        and (buckets.coverage >= 0.7).all()  # noqa: PLR2004
    )  # noqa: PLR2004


def compare_point_forecasts(naive: pd.DataFrame, lgbm: pd.DataFrame) -> pd.DataFrame:
    """G3 uses matched forecast rows so missing baseline anchors cannot bias it."""
    keys = ["issue_time", "target_time", "horizon"]
    left = naive[keys + ["y", "median"]]
    right = lgbm[keys + ["y", "median"]]
    paired = left.merge(right, on=keys, validate="one_to_one", suffixes=("_naive", "_lgbm"))
    if len(paired) != len(left) or len(paired) != len(right):
        raise ValueError("Model predictions must contain the same forecast keys")
    if not np.allclose(paired.y_naive, paired.y_lgbm, equal_nan=True):
        raise ValueError("Model predictions must share identical realized labels")
    finite = np.isfinite(
        paired[["y_naive", "median_naive", "median_lgbm"]].to_numpy(dtype=float)
    ).all(axis=1)
    paired = paired.loc[finite]
    groups = [(f"{lo}-{hi}", paired.loc[paired.horizon.between(lo, hi)]) for lo, hi in BUCKETS]
    groups.append(("all", paired))
    rows = []
    for label, frame in groups:
        baseline = mae(frame.y_naive, frame.median_naive)
        model = mae(frame.y_naive, frame.median_lgbm)
        rows.append(
            {
                "bucket": label,
                "n": len(frame),
                "mae_naive": baseline,
                "mae_lgbm": model,
                "improvement_percent": 100 * (baseline - model) / baseline
                if baseline > 0
                else np.nan,
                "g3_pass": bool(len(frame) and model < baseline),
            }
        )
    return pd.DataFrame(rows).set_index("bucket")
