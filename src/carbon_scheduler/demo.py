"""Build an offline raw-target demo without copying keys or unrelated files."""

import hashlib
import json
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from carbon_scheduler.config import Settings
from carbon_scheduler.ingest.store import read_hourly, write_hourly
from carbon_scheduler.models.registry import load_model, read_metadata
from carbon_scheduler.models.reporting import TARGETS


def _copy_weather_assets(region: str, settings: Settings, stage: Path) -> dict[str, str]:
    versions = {}
    for target in TARGETS:
        source = settings.models_dir / region / target
        pointer = source / "weather.json"
        if not pointer.is_file():
            continue
        choice = json.loads(pointer.read_text(encoding="utf-8"))
        if not isinstance(choice, dict) or choice.get("approved") is not True:
            raise ValueError("Demo weather variant must be explicitly approved")
        metadata = read_metadata(
            region,
            target,
            settings.models_dir,
            choice["version"],
            regions_path=settings.regions_path,
        )
        load_model(
            region,
            target,
            settings.models_dir,
            choice["version"],
            regions_path=settings.regions_path,
        )
        if metadata.get("exog_source") != "issue_vintage_forecast":
            raise ValueError("Demo weather variant requires issue-vintage provenance")
        version = metadata["version"]
        destination = stage / "models" / region / target / version
        destination.mkdir()
        for filename in ("model.joblib", "metadata.json"):
            shutil.copyfile(source / version / filename, destination / filename)
        shutil.copyfile(pointer, destination.parent / "weather.json")
        versions[target] = version
    if versions:
        destination = stage / "data" / "weather"
        destination.mkdir()
        shutil.copyfile(
            settings.data_dir / "weather" / f"{region}_forecast.parquet",
            destination / f"{region}_forecast.parquet",
        )
    return versions


@contextmanager
def _staging_directory(parent: Path) -> Iterator[Path]:
    # A normal mkdir inherits the workspace ACL on Windows. TemporaryDirectory's
    # private ACL survives rename and would prevent Git's other account reading it.
    directory = parent.resolve() / f".demo-stage-{uuid4().hex}"
    directory.mkdir()
    try:
        yield directory
    finally:
        if directory.parent == parent.resolve() and directory.name.startswith(".demo-stage-"):
            shutil.rmtree(directory)


def make_demo_assets(  # noqa: PLR0912
    region: str, settings: Settings, out_dir: Path, history_days: int = 400
) -> None:
    if history_days < 8:  # noqa: PLR2004
        raise ValueError("history_days must be at least 8 for weekly lag features")
    output = out_dir.resolve()
    if output.exists():
        raise FileExistsError("Demo output already exists; choose a new output directory")
    for source_root in (settings.data_dir.resolve(), settings.models_dir.resolve()):
        if output.is_relative_to(source_root) or source_root.is_relative_to(output):
            raise ValueError("Demo output must be separate from source data and model directories")
    frame = read_hourly(region, "raw", settings.data_dir, regions_path=settings.regions_path)
    if frame.empty:
        raise ValueError("No source observations for demo")
    frame = frame.iloc[-history_days * 24 :].copy()
    if len(frame) < 8 * 24:  # noqa: PLR2004
        raise ValueError("Demo snapshot needs at least 8 days of hourly history")
    metadata_by_target = {
        target: read_metadata(
            region, target, settings.models_dir, regions_path=settings.regions_path
        )
        for target in TARGETS
    }
    for target, metadata in metadata_by_target.items():
        load_model(
            region,
            target,
            settings.models_dir,
            metadata["version"],
            regions_path=settings.regions_path,
        )
        if metadata.get("data_source") != "raw":
            raise ValueError("Demo requires raw-trained models")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stage only newly created files. The user's existing output is never deleted.
    with _staging_directory(output.parent) as temporary:
        stage = Path(temporary) / "assets"
        stage.mkdir()
        write_hourly(frame, region, "raw", stage / "data", regions_path=settings.regions_path)
        for target, metadata in metadata_by_target.items():
            version = metadata["version"]
            source = settings.models_dir / region / target / version
            destination = stage / "models" / region / target / version
            destination.mkdir(parents=True)
            for filename in ("model.joblib", "metadata.json"):
                shutil.copyfile(source / filename, destination / filename)
            (destination.parent / "current.json").write_text(
                json.dumps({"version": version}) + "\n", encoding="utf-8"
            )
        weather_versions = _copy_weather_assets(region, settings, stage)
        manifest = {
            "region": region,
            "data_source": "raw",
            "history_days": history_days,
            "data_start": frame.index[0].isoformat(),
            "data_end": frame.index[-1].isoformat(),
            "models": {
                target: metadata["version"] for target, metadata in metadata_by_target.items()
            },
            "weather_models": weather_versions,
            "sha256": {
                str(path.relative_to(stage)).replace("\\", "/"): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in stage.rglob("*")
                if path.is_file()
            },
            "limitations": (
                "Frozen latest-revision snapshot; zero observation latency; "
                "carbon G4 missed nominal coverage."
            ),
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        # Verify the copied artifacts and snapshot together before publishing.
        from carbon_scheduler.api.service import ForecastService  # noqa: PLC0415

        service = ForecastService(
            settings.model_copy(
                update={
                    "data_dir": stage / "data",
                    "models_dir": stage / "models",
                    "demo_mode": True,
                }
            ),
            region,
        )
        healthy, reason = service.is_healthy()
        if not healthy:
            raise ValueError(f"Copied demo cannot serve forecasts: {reason}")
        for target, version in weather_versions.items():
            _, meta = service.forecast(target)
            if meta.model_version != version:
                raise ValueError("Copied demo weather variant fell back; snapshot is not valid")
        stage.rename(output)
