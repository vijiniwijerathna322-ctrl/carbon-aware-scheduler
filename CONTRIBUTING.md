# Contributing

This is primarily a portfolio/research project, but it follows a normal
open-source workflow and welcomes issues and pull requests.

## Setup

```bash
uv sync
uv run pytest -q
```

Use Python 3.11 or 3.12. Copy `.env.example` to `.env` for local
configuration; never commit API keys or real credentials.

## Before opening a pull request

Run the same gate CI runs:

```bash
make check   # ruff check, ruff format --check, mypy src, pytest
```

On Windows without `make`:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```

- Keep `mypy --strict` clean; don't add `# type: ignore` without a specific
  error code and a reason.
- Test coverage must stay at or above 80% (`pyproject.toml`'s
  `--cov-fail-under=80`); new code should carry its own tests, not rely on
  existing margin.
- Live tests (`-m live`) are excluded by default and require real external
  services (an EIA API key); don't make them part of the default gate.

## Design decisions

Non-trivial design choices are recorded as ADRs under `docs/adr/` — including
rejected experiments, not just adopted ones (see
[docs/adr/README.md](docs/adr/README.md) for the index). If your change makes
a real architectural choice (a new dependency, a new external integration, a
scope trade-off), add an ADR rather than only a code comment.

## Tone

This project is deliberately conservative about claims: results that miss a
declared gate are disclosed, not hidden, and features document their scope
limits (see any `notes` field in an API response, or `docs/model_card.md`).
Please keep that standard in new contributions — don't advertise a capability
the code doesn't actually validate.
