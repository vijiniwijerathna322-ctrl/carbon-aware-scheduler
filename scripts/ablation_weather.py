"""Reproducible, explicitly exploratory realized-weather CQR ablation."""

import argparse
import hashlib
import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_scheduler.config import get_settings
from carbon_scheduler.models.backtest import BacktestConfig, rolling_origin_backtest
from carbon_scheduler.models.evaluate import summarize
from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.lgbm import DEFAULT_PARAMS
from carbon_scheduler.models.reporting import TARGETS, _table, load_backtest_series
from carbon_scheduler.regions import load_regions
from carbon_scheduler.weather.client import WeatherClient


def fetch_weather(region: str, start: date, end: date, directory: Path) -> pd.DataFrame:
    frames = []
    client = WeatherClient(directory / "cache")
    try:
        for year in range(start.year, end.year + 1):
            first, last = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
            frame = client.fetch_history(
                load_regions()[region].weather_points, first, last, "archive"
            )
            frames.append(frame)
            print(
                f"Weather {year}: {len(frame)} hours, {frame.attrs['missing_cells']} missing cells",
                flush=True,
            )
    finally:
        client.close()
    result = pd.concat(frames)
    result.attrs.update(
        source="archive_exploratory",
        units=frames[0].attrs["units"],
        points=frames[0].attrs["points"],
        missing_cells=int(result.isna().sum().sum()),
    )
    directory.mkdir(parents=True, exist_ok=True)
    result.to_parquet(directory / f"{region}_archive.parquet")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="CISO")
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument(
        "--reuse-baseline",
        action="store_true",
        help="Reuse the exact previously evaluated CQR cohort after provenance/parameter checks.",
    )
    parser.add_argument(
        "--reuse-weather",
        action="store_true",
        help="Regenerate the report from existing weather predictions after provenance checks.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = _parse_args()
    settings = get_settings()
    region = load_regions()[args.region]
    first_series, _ = load_backtest_series(args.region, TARGETS[0], settings)
    weather = fetch_weather(
        args.region,
        first_series.index[0].date(),
        first_series.index[-1].date(),
        settings.data_dir / "weather",
    )
    if args.fetch_only:
        return
    sections = [
        "# Weather ablation: exploratory realized-weather covariates",
        "**This uses archive/reanalysis weather at future target times. It is a hindsight "
        "sensitivity experiment, not leakage-free deployment evidence. Train/serve skew "
        "remains: live weather forecasts have errors not represented here. No weather "
        "model will be promoted from these results.**",
        "Provider: [Open-Meteo](https://open-meteo.com/), CC BY 4.0. "
        "Four variables at three illustrative CISO points; missing hours/cells remain NaN. "
        "Historical Forecast probes had no 100 m wind in January 2021, and seamless "
        "history is not an issue-vintage 48-hour forecast panel.",
        "MAE, mean width and Winkler are in MWh for demand and gCO2e/kWh for intensity. "
        "Coverage in the tables is a fraction. Evaluation uses daily local-midnight "
        "issues over 2026-04-12 through 2026-10-12, seven 30-day refits, 90-day "
        "calibration, 400 trees, seed 42 and one training thread. Finite paired rows "
        "are shared by both variants; absent target labels are excluded, not filled.",
    ]
    for target in TARGETS:
        series, provenance = load_backtest_series(args.region, target, settings)
        stem = Path("reports") / f"backtest_{args.region}_{target}_cqr"
        metadata = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
        for key in ("input_sha256", "data_source", "factors_sha256"):
            if metadata.get(key) != provenance.get(key):
                raise ValueError(f"Baseline provenance mismatch: {key}")
        expected_params = {**DEFAULT_PARAMS, "seed": 42, "n_jobs": 1, "issue_step_h": 3}
        if (
            json.loads(metadata["model_parameters"]) != expected_params
            or metadata["calibration_days"] != 90  # noqa: PLR2004
            or metadata["timezone"] != region.timezone
        ):
            raise ValueError("Baseline parameters differ from this ablation")
        cfg = BacktestConfig(
            pd.Timestamp(metadata["test_start"]),
            pd.Timestamp(metadata["test_end"]),
            region.timezone,
        )
        baseline = (
            pd.read_parquet(stem.with_suffix(".parquet"))
            if args.reuse_baseline
            else rolling_origin_backtest(
                series, lambda target=target: ForecastModel(target, region.timezone), cfg
            )
        )
        weather_path = Path("reports") / f"ablation_weather_{args.region}_{target}.parquet"
        weather_hash = hashlib.sha256(
            (settings.data_dir / "weather" / f"{args.region}_archive.parquet").read_bytes()
        ).hexdigest()
        if args.reuse_weather:
            previous = json.loads(weather_path.with_suffix(".json").read_text(encoding="utf-8"))
            if (
                any(previous.get(key) != value for key, value in metadata.items())
                or previous.get("weather_sha256") != weather_hash
                or previous.get("experiment") != "archive_exploratory_not_deployment_evidence"
            ):
                raise ValueError("Weather report provenance differs from this experiment")
            prediction = pd.read_parquet(weather_path)
        else:
            print(f"Training weather CQR: {target}", flush=True)
            prediction = rolling_origin_backtest(
                series,
                lambda target=target: ForecastModel(
                    target, region.timezone, exog=weather, exog_source="archive_exploratory"
                ),
                cfg,
            )
        prediction.to_parquet(weather_path, index=False)
        keys = ["issue_time", "target_time", "horizon"]
        paired = baseline.merge(
            prediction, on=keys, suffixes=("_base", "_weather"), validate="one_to_one"
        )
        if len(paired) != len(baseline) or len(paired) != len(prediction):
            raise ValueError("Ablation cohorts differ")
        if not np.allclose(paired.y_base, paired.y_weather, equal_nan=True):
            raise ValueError("Ablation labels differ")
        valid = np.isfinite(
            paired[
                [
                    "y_base",
                    *[
                        f"{c}_{m}"
                        for m in ("base", "weather")
                        for c in ("lower", "median", "upper")
                    ],
                ]
            ]
        ).all(axis=1)
        tables = []
        for label in ("base", "weather"):
            frame = paired.loc[valid, keys].copy()
            for column in ("y", "lower", "median", "upper"):
                frame[column] = paired.loc[valid, f"{column}_{label}"].to_numpy()
            summary = summarize(frame)[["n", "mae", "coverage", "mean_width", "winkler"]]
            summary.index = [f"{label}/{bucket}" for bucket in summary.index]
            tables.append(summary)
        comparison = pd.concat(tables)
        base, variant = comparison.loc["base/all"], comparison.loc["weather/all"]
        sections.extend(
            [
                f"## {target}",
                f"Input SHA-256: `{provenance['input_sha256']}`. "
                f"Weather snapshot SHA-256: `{weather_hash}`.",
                _table(comparison),
                "Baseline reused: "
                + str(args.reuse_baseline)
                + "; identical input hashes, seed, parameters, refit configuration, "
                "forecast keys and labels verified.",
                f"Overall MAE changes from {base.mae:.2f} to {variant.mae:.2f} "
                f"({(variant.mae / base.mae - 1) * 100:+.2f}%). "
                f"Coverage changes from {base.coverage:.2%} to {variant.coverage:.2%}; "
                f"mean width changes from {base.mean_width:.2f} to {variant.mean_width:.2f}. "
                "G4's nominal 80% acceptance range is 77%-83%. "
                "These are hindsight-weather measurements and cannot validate live accuracy.",
            ]
        )
        details = {
            **metadata,
            "experiment": "archive_exploratory_not_deployment_evidence",
            "weather_sha256": weather_hash,
            "weather_metadata": weather.attrs,
            "issue_hour_local": cfg.issue_hour_local,
            "retrain_every_days": cfg.retrain_every_days,
        }
        weather_path.with_suffix(".json").write_text(
            json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    sections.extend(
        [
            "## Decision",
            "Retain the weather-free production models. These exploratory differences "
            "cannot establish operational improvement because future realized weather was "
            "supplied at prediction time. Carbon coverage must still be judged against G4; "
            "changing features on this previously examined test interval is not independent "
            "confirmation. An issue-vintage weather panel and a fresh holdout are required "
            "before promotion. Existing demo/API artifacts stay weather-free and offline.",
        ]
    )
    Path("docs/results/ablation-weather.md").write_text(
        "\n\n".join(sections) + "\n", encoding="utf-8"
    )
    print("Saved docs/results/ablation-weather.md", flush=True)


if __name__ == "__main__":
    main()
