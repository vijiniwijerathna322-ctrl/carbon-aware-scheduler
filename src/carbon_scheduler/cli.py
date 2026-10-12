"""Command-line entry point for carbon-aware scheduling."""

import json
from dataclasses import asdict

import typer

from carbon_scheduler import __version__
from carbon_scheduler.config import MissingApiKeyError, get_settings
from carbon_scheduler.ingest.eia_client import EiaAuthError, EiaRequestError
from carbon_scheduler.ingest.pipeline import G2_MAX_GAP_FRACTION, run_ingest
from carbon_scheduler.logging import configure_logging

app = typer.Typer(
    help="Carbon-aware energy scheduler.", no_args_is_help=True, pretty_exceptions_enable=False
)


@app.callback()
def main() -> None:
    """Configure shared command behavior."""
    configure_logging(get_settings().log_level)


@app.command()
def version() -> None:
    """Print the installed package version."""
    typer.echo(__version__)


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
