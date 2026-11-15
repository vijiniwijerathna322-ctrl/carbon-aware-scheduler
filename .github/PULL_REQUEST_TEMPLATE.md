## What changed and why

## Checklist

- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run mypy src` passes (strict mode)
- [ ] `uv run pytest -q` passes, coverage stays ≥ 80%
- [ ] New non-trivial design decisions are recorded in `docs/adr/` (and listed
      in `docs/adr/README.md`)
- [ ] Any new claim or metric in docs/README states its scope and limits,
      consistent with the rest of this project

## Evidence

If this changes measured results (backtest, calibration, scheduling replay,
monitoring), link the regenerated report(s) under `docs/results/` or
`reports/`.
