"""Versioned local artifacts with atomic current pointers and integrity checks."""

import hashlib
import json
import os
import platform
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp
from typing import Any
from uuid import uuid4

import joblib  # type: ignore[import-untyped]
import numpy as np
import pandas as pd

from carbon_scheduler.config import PROJECT_ROOT
from carbon_scheduler.features.build import FEATURE_COLUMNS
from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.regions import load_regions

VERSION_PATTERN = r"\d{8}T\d{6}Z-[a-f0-9]{8}"


class ModelNotFoundError(FileNotFoundError):
    """A requested local artifact is unavailable."""


class ModelIncompatibleError(RuntimeError):
    """Artifact contract, path or integrity does not match this runtime."""


def _base(region: str, target: str, models_dir: Path) -> Path:
    load_regions()[region]
    if target not in ("demand_mwh", "carbon_intensity_g_per_kwh"):
        raise ModelIncompatibleError("Unsupported target")
    root = models_dir.resolve()
    path = root / region / target
    if not path.resolve().is_relative_to(root):
        raise ModelIncompatibleError("Artifact path escapes configured models directory")
    return path


def _versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        **{name: package_version(name) for name in ("lightgbm", "pandas", "numpy", "joblib")},
    }


def _safe_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    if isinstance(value, np.generic):
        return _safe_json(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _atomic_json(path: Path, values: Mapping[str, Any]) -> None:
    with NamedTemporaryFile(dir=path.parent, suffix=".json", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(
            json.dumps(_safe_json(values), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_model(
    model: ForecastModel,
    region: str,
    models_dir: Path,
    metrics: Mapping[str, Any] | None = None,
    data_end: pd.Timestamp | None = None,
) -> Path:
    base = _base(region, model.target, models_dir)
    metadata = model.metadata()
    if data_end is not None and data_end.isoformat() != metadata["data_end"]:
        raise ValueError("data_end must match the fitted model's actual history end")
    now = datetime.now(UTC)
    identifier = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    base.mkdir(parents=True, exist_ok=True)
    path = base / identifier
    staging = Path(mkdtemp(dir=base, prefix=".tmp-"))
    try:
        joblib.dump(model, staging / "model.joblib", compress=3)
        try:
            git_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            git_sha = "unknown"
        metadata.update(
            region=region,
            version=identifier,
            trained_at=now.isoformat(),
            versions=_versions(),
            git_sha=git_sha,
            metrics=dict(metrics or {}),
            model_sha256=hashlib.sha256((staging / "model.joblib").read_bytes()).hexdigest(),
        )
        _atomic_json(staging / "metadata.json", metadata)
        os.replace(staging, path)
        _atomic_json(base / "current.json", {"version": identifier})
    finally:
        if staging.exists():
            (staging / "model.joblib").unlink(missing_ok=True)
            (staging / "metadata.json").unlink(missing_ok=True)
            staging.rmdir()
    return path


def _artifact(region: str, target: str, models_dir: Path, version: str | None) -> Path:
    base = _base(region, target, models_dir)
    hint = f"Model unavailable for {region}/{target}; run carbon-scheduler train --region {region}"
    if version is None:
        try:
            version = json.loads((base / "current.json").read_text(encoding="utf-8"))["version"]
        except FileNotFoundError as error:
            raise ModelNotFoundError(hint) from error
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise ModelIncompatibleError("Invalid current model pointer") from error
    if not isinstance(version, str) or re.fullmatch(VERSION_PATTERN, version) is None:
        raise ModelIncompatibleError("Invalid model version identifier")
    path = base / version
    if not path.resolve().is_relative_to(models_dir.resolve()):
        raise ModelIncompatibleError("Model version escapes configured registry")
    if not (path / "model.joblib").is_file() or not (path / "metadata.json").is_file():
        raise ModelNotFoundError(hint)
    for filename in ("model.joblib", "metadata.json"):
        if not (path / filename).resolve().is_relative_to(models_dir.resolve()):
            raise ModelIncompatibleError("Model file escapes configured registry")
    return path


def read_metadata(
    region: str,
    target: str,
    models_dir: Path,
    version: str | None = None,
) -> dict[str, Any]:
    path = _artifact(region, target, models_dir, version)
    try:
        result = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ModelIncompatibleError("Invalid model metadata JSON") from error
    if (
        not isinstance(result, dict)
        or result.get("region") != region
        or result.get("target") != target
    ):
        raise ModelIncompatibleError("Metadata region/target mismatch")
    return dict(result)


def load_model(
    region: str,
    target: str,
    models_dir: Path,
    version: str | None = None,
) -> ForecastModel:
    path = _artifact(region, target, models_dir, version)
    metadata = read_metadata(region, target, models_dir, path.name)
    if metadata.get("feature_columns") != FEATURE_COLUMNS:
        raise ModelIncompatibleError(
            "feature_columns mismatch; retrain with the current feature builder"
        )
    for name, current in _versions().items():
        saved = metadata.get("versions", {}).get(name)
        compatible = (
            saved == current
            if name != "python"
            else isinstance(saved, str) and saved.split(".")[:2] == current.split(".")[:2]
        )
        if not compatible:
            raise ModelIncompatibleError(f"{name} version mismatch; retrain in this environment")
    digest = hashlib.sha256((path / "model.joblib").read_bytes()).hexdigest()
    if digest != metadata.get("model_sha256"):
        raise ModelIncompatibleError("Model digest mismatch; artifact is incomplete or corrupted")
    try:
        model = joblib.load(path / "model.joblib")
    except Exception as error:
        raise ModelIncompatibleError("Cannot deserialize local model; retrain") from error
    if (
        not isinstance(model, ForecastModel)
        or model.target != target
        or model.metadata()["feature_columns"] != FEATURE_COLUMNS
    ):
        raise ModelIncompatibleError("Serialized model does not match its metadata")
    return model
