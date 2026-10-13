"""Current artifact replay: never score issues preceding the model fit cutoff."""

import html
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
import pandas as pd
from pydantic import TypeAdapter

from carbon_scheduler.config import Settings
from carbon_scheduler.models.backtest import BacktestConfig, _issue_times, _validate_prediction
from carbon_scheduler.models.registry import load_model, read_metadata
from carbon_scheduler.models.reporting import TARGETS, load_backtest_series
from carbon_scheduler.monitoring.drift import Status, classify_psi, ks_drift, psi
from carbon_scheduler.monitoring.performance import (
    CoverageStatus,
    coverage_status,
    mae_ratio_status,
)
from carbon_scheduler.regions import load_regions

PRIORITY = {"ok": 0, "insufficient_data": 1, "warn": 2, "alert": 3}
LIMITATIONS = (
    "Latest-revision raw snapshot; zero observation latency assumed. "
    "Only issues at or after the artifact fit_end are scored; one latest eligible "
    "forecast per realized target hour. KS and binomial p-values are operational "
    "diagnostics: serial dependence, ties, seasonality and multiple tests remain. "
    "Calibration metrics are never used as a held-out MAE baseline."
)


@dataclass(frozen=True)
class MonitorReport:
    region: str
    generated_at: datetime
    model_version: dict[str, str]
    window_start: datetime
    window_end: datetime
    feature_drift: dict[str, dict[str, Any]]
    coverage: dict[str, CoverageStatus]
    mae_ratio: dict[str, float | None]
    status: Status
    reasons: list[str]
    replay: dict[str, dict[str, Any]]
    baseline: dict[str, dict[str, Any]]
    provenance: dict[str, dict[str, str]]
    limitations: str = LIMITATIONS


def _worst(statuses: list[Status]) -> Status:
    return max(statuses, key=lambda status: PRIORITY[status]) if statuses else "insufficient_data"


def _baseline_mae(  # noqa: PLR0913, PLR0917
    target: str,
    region: str,
    settings: Settings,
    start: pd.Timestamp,
    metadata: dict[str, Any],
    provenance: dict[str, str],
) -> tuple[float | None, int, str]:  # noqa: PLR0913, PLR0917
    path = settings.reports_dir / f"backtest_{region}_{target}_cqr.parquet"
    try:
        info = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        expected = {
            **metadata["lgbm_parameters"],
            "seed": metadata["seed"],
            "n_jobs": 1,
            "issue_step_h": metadata["issue_step_h"],
        }
        if (
            info.get("data_source") != "raw"
            or info.get("experiment")
            or info.get("exog_columns")
            or info.get("weather_metadata")
            or info.get("factors_sha256") != provenance.get("factors_sha256")
            or info.get("timezone") != metadata["tz"]
            or info.get("calibration_days") != metadata["calibration_days"]
            or json.loads(info["model_parameters"]) != expected
        ):
            return None, 0, "Baseline provenance or model configuration differs"
        frame = pd.read_parquet(path)
        # Do not dilute a recent shift with those same points in its baseline.
        frame = frame.loc[frame.target_time < start].sort_values("issue_time")
        frame = frame.drop_duplicates("target_time", keep="last")
        valid = pd.Series(
            np.isfinite(frame[["y", "median"]].to_numpy(dtype=float)).all(axis=1),
            index=frame.index,
        )
        n = int(valid.sum())
        if n < 100:  # noqa: PLR2004
            return None, n, "Fewer than 100 earlier held-out baseline points"
        return (
            float((frame.loc[valid, "y"] - frame.loc[valid, "median"]).abs().mean()),
            n,
            ("Earlier raw CQR backtest; latest forecast per target hour; excludes current window"),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None, 0, "Earlier held-out CQR baseline unavailable"


def _features(series: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "target": series,
            "y_issue": series,
            "roll_mean_24": series.rolling(24, min_periods=24).mean(),
            "roll_std_24": series.rolling(24, min_periods=24).std(),
        }
    )


def _drift(reference: pd.Series, current: pd.Series) -> dict[str, Any]:
    ref, cur = reference.to_numpy(dtype=float), current.to_numpy(dtype=float)
    n_ref, n_cur = int(np.isfinite(ref).sum()), int(np.isfinite(cur).sum())
    result: dict[str, Any] = {
        "n_reference": n_ref,
        "n_current": n_cur,
        "excluded_reference": len(ref) - n_ref,
        "excluded_current": len(cur) - n_cur,
        "overlap_hours": len(reference.index.intersection(current.index)),
        "psi": None,
        "ks_statistic": None,
        "ks_p_value": None,
        "status": "insufficient_data",
    }
    if min(n_ref, n_cur) < 100:  # noqa: PLR2004
        return result
    value = psi(ref, cur)
    statistic, p_value = ks_drift(ref, cur)
    result.update(
        psi=value,
        ks_statistic=statistic,
        ks_p_value=p_value,
        status=_worst([classify_psi(value), "alert" if p_value < 0.01 else "ok"]),  # noqa: PLR2004
    )
    return result


def _replay(
    series: pd.Series,
    model: Any,
    cfg: BacktestConfig,
    fit_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    issues = _issue_times(
        BacktestConfig(cfg.test_start - pd.Timedelta(hours=48), cfg.test_end, cfg.tz)
    )
    eligible = issues[issues >= fit_end]
    frames = []
    for issue in eligible:
        prediction = model.predict(series.loc[:issue].copy(), issue)
        _validate_prediction(prediction, issue)
        prediction = prediction.copy()
        prediction["issue_time"] = issue
        prediction["y"] = series.reindex(pd.DatetimeIndex(prediction.target_time)).to_numpy()
        frames.append(
            prediction.loc[
                (prediction.target_time >= cfg.test_start)
                & (prediction.target_time <= cfg.test_end)
            ]
        )
    frame = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(
            columns=["issue_time", "target_time", "horizon", "lower", "median", "upper", "y"]
        )
    )
    total = len(frame)
    frame = frame.sort_values("issue_time").drop_duplicates("target_time", keep="last")
    valid = np.isfinite(frame[["y", "lower", "median", "upper"]].to_numpy(dtype=float)).all(axis=1)
    counts = {
        "issues_considered": len(issues),
        "issues_skipped_fit_end": len(issues) - len(eligible),
        "issues_replayed": len(eligible),
        "prediction_rows": total,
        "duplicate_target_rows_removed": total - len(frame),
        "excluded_nonfinite": int((~valid).sum()),
        "usable_points": int(valid.sum()),
        "fit_end": fit_end.isoformat(),
        "last_finite_observation": str(series.last_valid_index()),
    }
    return frame.loc[valid].copy(), counts


def build_monitor_report(  # noqa: PLR0915, PLR0912
    region: str,
    settings: Settings,
    now: datetime | None = None,
) -> MonitorReport:
    generated = pd.Timestamp(now or datetime.now(UTC))
    if generated.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    generated = generated.tz_convert("UTC")
    tz = load_regions(settings.regions_path)[region].timezone
    ratios: dict[str, float | None] = {}
    versions, drifts, coverages, replay, baselines, provenance_all = (
        {},
        {},
        {},
        {},
        {},
        {},
    )
    statuses: list[Status] = []
    reasons: list[str] = []
    window_start = window_end = generated.floor("h")
    for target in TARGETS:
        series, provenance = load_backtest_series(region, target, settings)
        series = series.loc[: generated.floor("h")]
        if series.empty:
            raise ValueError("No observations by the requested time")
        window_end = pd.Timestamp(series.index[-1])
        window_start = window_end - pd.Timedelta(days=14) + pd.Timedelta(hours=1)
        if not settings.demo_mode and generated - window_end > pd.Timedelta(
            hours=settings.max_data_age_hours
        ):
            statuses.append("warn")
            reasons.append(
                f"{target}: input snapshot is stale; window ends at {window_end.isoformat()}."
            )
        metadata = read_metadata(
            region, target, settings.models_dir, regions_path=settings.regions_path
        )
        pointer = settings.models_dir / region / target / "weather.json"
        if pointer.is_file():
            choice = json.loads(pointer.read_text(encoding="utf-8"))
            if isinstance(choice, dict) and choice.get("approved") is True:
                raise ValueError(
                    "Approved weather variants require issue-vintage forecast logs for monitoring"
                )
        if metadata.get("data_source") != "raw" or metadata.get("exog_columns"):
            raise ValueError("Monitoring requires raw-trained weather-free artifacts")
        if target == TARGETS[1] and metadata.get("factors_sha256") != provenance.get(
            "factors_sha256"
        ):
            raise ValueError("Monitoring carbon factors differ from the artifact")
        fit_end = pd.Timestamp(metadata["fit_end"])
        if fit_end > generated:
            raise ValueError("Requested time precedes the model fit cutoff")
        model = load_model(
            region,
            target,
            settings.models_dir,
            metadata["version"],
            regions_path=settings.regions_path,
        )
        versions[target], provenance_all[target] = metadata["version"], provenance
        features = _features(series)
        reference = features.loc[fit_end - pd.Timedelta(days=180) + pd.Timedelta(hours=1) : fit_end]
        current = features.reindex(pd.date_range(window_start, window_end, freq="h"))
        for name in features:
            key = f"{target}/{name}"
            drifts[key] = _drift(reference[name], current[name])
            status = drifts[key]["status"]
            statuses.append(status)
            if status != "ok":
                reasons.append(f"{key}: input drift {status} (PSI/KS; missing values excluded).")
        frame, replay[target] = _replay(
            series, model, BacktestConfig(window_start, window_end, tz), fit_end
        )
        coverage = coverage_status(
            frame.y.to_numpy(dtype=float),
            frame.lower.to_numpy(dtype=float),
            frame.upper.to_numpy(dtype=float),
            nominal=1 - float(metadata["alpha"]),
        )
        coverages[target] = coverage
        statuses.append(coverage.status)
        if coverage.status != "ok":
            reasons.append(
                f"{target}: coverage {coverage.status}; {coverage.n} unique realized hours "
                "from issues at/after fit_end (minimum 100)."
            )
        baseline, n_baseline, scope = _baseline_mae(
            target, region, settings, window_start, metadata, provenance
        )
        recent = float((frame.y - frame["median"]).abs().mean()) if len(frame) else None
        baselines[target] = {"mae": baseline, "n": n_baseline, "scope": scope, "recent_mae": recent}
        ratios[target] = None
        if coverage.n < 100 or baseline is None or recent is None:  # noqa: PLR2004
            statuses.append("insufficient_data")
            reasons.append(f"{target}: MAE comparison insufficient_data; {scope}.")
        else:
            ratios[target] = recent / baseline if baseline else (1.0 if recent == 0 else None)
            status = mae_ratio_status(recent, baseline)
            statuses.append(status)
            if status != "ok":
                reasons.append(
                    f"{target}: MAE ratio {status}; recent {recent:.3f}, baseline {baseline:.3f}."
                )
    return MonitorReport(
        region,
        generated.to_pydatetime(),
        versions,
        window_start.to_pydatetime(),
        window_end.to_pydatetime(),
        drifts,
        coverages,
        ratios,
        _worst(statuses),
        reasons,
        replay,
        baselines,
        provenance_all,
    )


def to_json(report: MonitorReport) -> str:
    return (
        json.dumps(
            asdict(report),
            indent=2,
            allow_nan=False,
            default=lambda value: value.isoformat().replace("+00:00", "Z"),
        )
        + "\n"
    )


def to_html(report: MonitorReport) -> str:
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in report.reasons)
    rows = []
    for target, coverage in report.coverage.items():
        percent = "N/A" if coverage.coverage is None else f"{coverage.coverage:.2%}"
        p_value = "N/A" if coverage.p_value is None else f"{coverage.p_value:.3g}"
        ratio = report.mae_ratio[target]
        ratio_label = "N/A" if ratio is None else f"{ratio:.2f}"
        rows.append(
            f"<tr><td>{html.escape(target)}</td><td>{coverage.n}</td>"
            f"<td>{percent}</td><td>{p_value}</td><td>{ratio_label}</td>"
            f"<td>{coverage.status}</td></tr>"
        )
    drift_rows = []
    for key, drift in report.feature_drift.items():
        value = "N/A" if drift["psi"] is None else f"{drift['psi']:.3f}"
        p_value = "N/A" if drift["ks_p_value"] is None else f"{drift['ks_p_value']:.3g}"
        drift_rows.append(
            f"<tr><td>{html.escape(key)}</td><td>{drift['n_reference']}</td>"
            f"<td>{drift['n_current']}</td><td>{drift['excluded_current']}</td>"
            f"<td>{value}</td><td>{p_value}</td><td>{drift['status']}</td></tr>"
        )
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Model monitoring</title><style>body{font:16px system-ui;max-width:1000px;"
        "margin:2rem auto;padding:0 1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;"
        "background:#f2f4f8;padding:1rem}li{margin:.5rem 0}"
        "table{border-collapse:collapse;font-size:14px;width:100%}"
        "th,td{padding:.5rem;border-bottom:1px solid #ccd3df;text-align:left}"
        ".table{overflow:auto}summary{cursor:pointer;padding:1rem 0}</style>"
        f"<h1>{html.escape(report.region)} monitoring: {report.status}</h1>"
        f"<p>Window: {report.window_start.isoformat()} to {report.window_end.isoformat()}"
        f"<br>Generated: {report.generated_at.isoformat()}</p>"
        f"<p>{html.escape(report.limitations)}</p><ul>{reasons}</ul>"
        "<h2>Performance on unique realized hours</h2><div class='table'><table>"
        "<tr><th>Target</th><th>n</th><th>Coverage</th><th>Binomial p</th>"
        "<th>MAE ratio</th><th>Coverage status</th></tr>"
        + "".join(rows)
        + "</table></div><h2>Input drift</h2><div class='table'><table>"
        "<tr><th>Feature</th><th>Reference n</th><th>Current n</th><th>Missing current</th>"
        "<th>PSI</th><th>KS p</th><th>Status</th></tr>" + "".join(drift_rows) + "</table></div>"
        f"<details><summary>Full diagnostics JSON, versions and counts</summary>"
        f"<pre>{html.escape(to_json(report))}</pre></details></html>"
    )


def write_monitor_report(
    report: MonitorReport, directory: Path, *, regions_path: Path | None = None
) -> Path:
    load_regions(regions_path)[report.region]
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"monitor_{report.region}.json"
    for path, content in (
        (output.with_suffix(".html"), to_html(report)),
        (output, to_json(report)),
    ):
        with NamedTemporaryFile(dir=directory, suffix=path.suffix, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return output


def _reject_constant(value: str) -> None:
    raise ValueError(f"Nonfinite JSON constant: {value}")


def read_monitor_report(path: Path, region: str) -> dict[str, Any]:
    content = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    report = TypeAdapter(MonitorReport).validate_python(content)
    if (
        report.region != region
        or set(report.model_version) != set(TARGETS)
        or any(
            value.tzinfo is None
            for value in (report.generated_at, report.window_start, report.window_end)
        )
        or report.window_start > report.window_end
        or report.window_end > report.generated_at
    ):
        raise ValueError("Invalid monitor report identity or timestamps")
    return dict(content)
