"""Command-line entry point for carbon-aware scheduling."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from carbon_scheduler import __version__
from carbon_scheduler.carbon.dataset import build_dataset as build_processed_dataset
from carbon_scheduler.config import MissingApiKeyError, get_settings
from carbon_scheduler.demo import make_demo_assets
from carbon_scheduler.ingest.eia_client import EiaAuthError, EiaRequestError
from carbon_scheduler.ingest.pipeline import G2_MAX_GAP_FRACTION, run_ingest
from carbon_scheduler.logging import configure_logging
from carbon_scheduler.models.reporting import run_backtest
from carbon_scheduler.models.training import train_region
from carbon_scheduler.monitoring.report import build_monitor_report, write_monitor_report
from carbon_scheduler.scheduler.reporting import run_schedule_backtest

app = typer.Typer(
    help="Carbon-aware energy scheduler.", no_args_is_help=True, pretty_exceptions_enable=False
)


@app.command()
def monitor(
    region: str = typer.Option("CISO"),
    reports_dir: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Write drift and strictly post-fit performance diagnostics; alerts exit 2."""
    try:
        settings = get_settings()
        if reports_dir is not None:
            settings = settings.model_copy(update={"reports_dir": reports_dir.resolve()})
        report = build_monitor_report(region, settings)
        path = write_monitor_report(report, settings.reports_dir)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        typer.echo(f"Monitor failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Monitoring {report.status}: {path}")
    if report.status == "alert":
        raise typer.Exit(code=2)


@app.command()
def make_demo(
    region: str = typer.Option("CISO"),
    out_dir: Annotated[Path, typer.Option()] = Path("demo"),
    history_days: int = typer.Option(400, min=8),
) -> None:
    """Copy current raw-model artifacts into a new offline demo directory."""
    try:
        make_demo_assets(region, get_settings(), out_dir, history_days)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"Make demo failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Offline demo: {out_dir}")


@app.command()
def schedule_backtest(
    region: str = typer.Option("CISO"),
    reports_dir: Annotated[Path, typer.Option()] = Path("reports"),
) -> None:
    """Replay both scheduling strategies using saved CQR carbon forecasts."""
    try:
        path = run_schedule_backtest(region, get_settings(), reports_dir)
    except (OSError, ValueError, KeyError) as error:
        typer.echo(f"Schedule backtest failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Scheduling report: {path}")


@app.command()
def train(
    region: str = typer.Option("CISO"),
    fit_end: str | None = typer.Option(None),
) -> None:
    """Train both raw-target calibrated models and save local artifacts."""
    try:
        timestamp = None
        if fit_end is not None:
            import pandas as pd  # noqa: PLC0415

            timestamp = pd.Timestamp(fit_end)
            timestamp = (
                timestamp.tz_localize("UTC")
                if timestamp.tz is None
                else timestamp.tz_convert("UTC")
            )
        paths = train_region(region, get_settings(), fit_end=timestamp)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"Train failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    for target, path in paths.items():
        typer.echo(f"Saved {target}: {path}")


@app.command()
def backtest(
    region: str = typer.Option("CISO"),
    target: str = typer.Option("carbon_intensity_g_per_kwh"),
    model: str = typer.Option("naive"),
    data_source: str = typer.Option("raw"),
    reports_dir: Annotated[Path, typer.Option()] = Path("reports"),
) -> None:
    """Compare chronological forecasts using raw observations by default."""
    try:
        if data_source not in ("raw", "processed"):
            raise ValueError("data-source must be raw or processed")
        path = run_backtest(
            region,
            target,
            model,
            get_settings(),
            reports_dir=reports_dir,
            data_source="raw" if data_source == "raw" else "processed",
        )
    except (OSError, ValueError) as error:
        typer.echo(f"Backtest failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Backtest report: {path}")
    typer.echo(f"Predictions: {path.with_suffix('.parquet')}")


@app.callback()
def main() -> None:
    """Configure shared command behavior."""
    configure_logging(get_settings().log_level)


@app.command()
def version() -> None:
    """Print the installed package version."""
    typer.echo(__version__)


@app.command()
def build_dataset(
    region: str = typer.Option("CISO"),
    factors_path: Annotated[Path, typer.Option()] = Path("config/emission_factors.yaml"),
) -> None:
    """Build processed intensity and coverage diagnostics from interim data."""
    try:
        path = build_processed_dataset(region, get_settings(), factors_path)
    except (OSError, ValueError) as error:
        typer.echo(f"Build dataset failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Processed dataset: {path}")
    typer.echo(f"Carbon quality report: {path.with_name('carbon-quality-report.json')}")


@app.command()
def ingest(
    region: str = typer.Option("CISO"),
    start: str = typer.Option("2021-01-01T00"),
    end: str | None = typer.Option(None),
) -> None:
    """Fetch inclusive UTC hours and report completeness."""
    try:
        report = run_ingest(region, start, end, get_settings())
    except (MissingApiKeyError, EiaAuthError, EiaRequestError, ValueError) as error:
        typer.echo(f"Ingest failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(asdict(report), indent=2))
    passed = report.n_rows > 0 and report.gap_fraction < G2_MAX_GAP_FRACTION
    typer.echo(f"G2: {'PASS' if passed else 'FAIL'}")
    if not passed:
        raise typer.Exit(code=2)
