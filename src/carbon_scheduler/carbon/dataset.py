"""Build a generation-based proxy with explicit coverage and provenance."""

import hashlib
import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from carbon_scheduler.carbon.factors import load_emission_factors
from carbon_scheduler.carbon.intensity import compute_intensity
from carbon_scheduler.config import PROJECT_ROOT, Settings
from carbon_scheduler.ingest.store import hourly_path, read_hourly, write_hourly


def _write_report(path: Path, report: dict[str, object]) -> None:
    content = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    with NamedTemporaryFile(dir=path.parent, suffix=".json", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_dataset(
    region: str,
    settings: Settings,
    factors_path: Path = Path("config/emission_factors.yaml"),
) -> Path:
    """Append intensity and observed-mix diagnostics; no API access required.

    Coverage describes observed positive generation only. Missing fuel columns
    are listed separately; missing-cell counts cover present included columns.
    """
    frame = read_hourly(region, "interim", settings.data_dir)
    resolved = factors_path if factors_path.is_absolute() else PROJECT_ROOT / factors_path
    factors = load_emission_factors(resolved)
    frame["carbon_intensity_g_per_kwh"] = compute_intensity(frame, factors)
    fuels = {
        column: match.group(1)
        for column in frame.columns
        if isinstance(column, str) and (match := re.fullmatch(r"gen_(.+)_mwh", column))
    }
    included = [column for column, code in fuels.items() if code in factors.factors]
    excluded = [column for column, code in fuels.items() if code in factors.excluded]
    generation = frame[list(fuels)].astype("float64")
    positive = generation.clip(lower=0)
    covered = positive[included].sum(axis=1, min_count=1)
    omitted = positive[excluded].sum(axis=1, min_count=1)
    total = positive.sum(axis=1, min_count=1)
    frame["carbon_covered_generation_mwh"] = covered
    frame["carbon_excluded_generation_mwh"] = omitted
    frame["carbon_observed_coverage_fraction"] = covered.div(total.where(total > 0))
    frame["carbon_missing_fuel_count"] = generation[included].isna().sum(axis=1)
    frame["carbon_negative_generation_count"] = generation.lt(0).sum(axis=1)
    report: dict[str, object] = {
        "schema_version": 1,
        "region": region,
        "unit": "gCO2e/kWh",
        "source": factors.source,
        "factors": dict(factors.factors),
        "configured_exclusions": sorted(factors.excluded),
        "included_codes": sorted(fuels[column] for column in included),
        "excluded_codes": sorted(fuels[column] for column in excluded),
        "absent_factor_codes": sorted(set(factors.factors) - set(fuels.values())),
        "coverage_scope": "Observed positive fuel generation; unobserved generation is unknown.",
        "input_sha256": hashlib.sha256(
            hourly_path(region, "interim", settings.data_dir).read_bytes()
        ).hexdigest(),
        "factors_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "quality": {
            "n_rows": len(frame),
            "missing_intensity_hours": int(frame.carbon_intensity_g_per_kwh.isna().sum()),
            "partial_included_mix_hours": int(frame.carbon_missing_fuel_count.gt(0).sum()),
            "missing_included_fuel_cells": int(frame.carbon_missing_fuel_count.sum()),
            "negative_generation_cells": int(frame.carbon_negative_generation_count.sum()),
            "covered_generation_mwh": float(covered.sum()),
            "excluded_generation_mwh": float(omitted.sum()),
        },
    }
    path = write_hourly(frame, region, "processed", settings.data_dir)
    _write_report(path.with_name("carbon-quality-report.json"), report)
    return path
