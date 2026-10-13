# Frozen portfolio figure inputs

These are the saved CISO evaluation outputs used by the portfolio figures.
They include chronological CQR and naive backtests, scheduler comparisons,
and the isolated drift simulation. They contain no API key and require no
live ingestion to reproduce the plots.

From the repository root, run `uv run python scripts/make_figures.py`.
The default reads this directory and writes the five PNGs and provenance
manifest under `docs/figures`, plus `docs/results/portfolio-summary.json`.
Use `--reports-dir reports` to plot a new local evaluation instead.

See `docs/model_card.md` and `docs/datasheet.md` for evaluation periods,
source attribution, coverage limitations, and the carbon proxy definition.
These outputs preserve the source-data terms described in the datasheet;
the repository's MIT license applies to the code.
