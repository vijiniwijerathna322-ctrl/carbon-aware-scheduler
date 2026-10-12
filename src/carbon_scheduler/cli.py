"""Command-line entry point for carbon-aware scheduling."""

import typer

from carbon_scheduler import __version__
from carbon_scheduler.config import get_settings
from carbon_scheduler.logging import configure_logging

app = typer.Typer(help="Carbon-aware energy scheduler.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Configure shared command behavior."""
    configure_logging(get_settings().log_level)


@app.command()
def version() -> None:
    """Print the installed package version."""
    typer.echo(__version__)
