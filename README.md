# Carbon-Aware Energy Scheduler

Forecast grid demand and carbon intensity, then schedule flexible jobs with honest uncertainty.
Implementation follows the [master plan](plans/2026-10-11-00-master-plan.md).

## Development

Use Python 3.11 or 3.12 and uv. Run `uv sync`, then `make check`.
On Windows without make, run `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy src`, and `uv run pytest -q`.
Copy `.env.example` to `.env` for local configuration; never commit API keys.
Live tests are excluded by default; explicitly select them with `uv run pytest -m live`.
