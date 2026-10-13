"""Prepare a byte-exact, credential-free monitoring bundle for human review."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_scheduler.config import Settings, get_settings
from carbon_scheduler.models.registry import load_model, read_metadata
from carbon_scheduler.models.reporting import TARGETS
from carbon_scheduler.regions import load_regions


def prepare_bundle(region: str, settings: Settings, output: Path) -> dict:
    """Validate selected artifacts and backtest contracts; never publish or promote."""
    configured = load_regions(settings.regions_path)[region]
    if output.exists():
        raise FileExistsError("Deployment output already exists; choose a new directory")
    sources, versions, counts = {}, {}, {}
    for target in TARGETS:
        metadata = read_metadata(
            region, target, settings.models_dir, regions_path=settings.regions_path
        )
        load_model(region, target, settings.models_dir, regions_path=settings.regions_path)
        if metadata.get("data_source") != "raw" or metadata.get("exog_columns"):
            raise ValueError("Monitoring deployment requires raw weather-free artifacts")
        base = settings.models_dir / region / target
        weather = base / "weather.json"
        if weather.exists() and json.loads(weather.read_text()).get("approved") is True:
            raise ValueError("Approved weather variants require forecast-vintage monitoring logs")
        version = metadata["version"]
        versions[target] = version
        for filename in ("model.joblib", "metadata.json"):
            relative = Path("models") / region / target / version / filename
            sources[relative] = base / version / filename
        sources[Path("models") / region / target / "current.json"] = base / "current.json"
        stem = settings.reports_dir / f"backtest_{region}_{target}_cqr"
        report = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
        parameters = {
            **metadata["lgbm_parameters"],
            "seed": metadata["seed"],
            "n_jobs": 1,
            "issue_step_h": metadata["issue_step_h"],
        }
        if (
            report.get("data_source") != "raw"
            or any(report.get(key) for key in ("experiment", "exog_columns", "weather_metadata"))
            or report.get("timezone") != configured.timezone
            or report.get("calibration_days") != metadata["calibration_days"]
            or json.loads(report.get("model_parameters", "{}")) != parameters
            or report.get("factors_sha256") != metadata.get("factors_sha256")
        ):
            raise ValueError("Held-out baseline provenance/configuration differs from model")
        predictions = pd.read_parquet(stem.with_suffix(".parquet"))
        required = {"issue_time", "target_time", "horizon", "y", "lower", "median", "upper"}
        if required - set(predictions):
            raise ValueError("Held-out baseline is missing prediction columns")
        finite = np.isfinite(predictions[["y", "median"]].to_numpy(dtype=float)).all(axis=1)
        counts[target] = int(finite.sum())
        if counts[target] < 100:  # noqa: PLR2004
            raise ValueError("Need at least 100 finite held-out baseline rows")
        for suffix in ("parquet", "json"):
            source = stem.with_suffix(f".{suffix}")
            sources[Path("reports") / source.name] = source
    # Validate everything before creating output. Copy only the explicit allowlist.
    output.mkdir(parents=True)
    for relative, source in sources.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    manifest = {
        "region": region,
        "models": versions,
        "finite_baseline_rows": counts,
        "approval": "pending human review; not published or promoted",
        "sha256": {
            relative.as_posix(): hashlib.sha256((output / relative).read_bytes()).hexdigest()
            for relative in sources
        },
    }
    (output / "deployment-manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_bundle(args.region, get_settings(), args.output)
    print(json.dumps({"output": str(args.output), "models": manifest["models"]}, indent=2))
