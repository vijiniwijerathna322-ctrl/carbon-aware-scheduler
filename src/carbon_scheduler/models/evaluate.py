"""Horizon-bucket summaries with explicit point and interval sample counts."""

from collections.abc import Sequence

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
