UV ?= uv

.PHONY: lint test check
lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy src

test:
	$(UV) run pytest -q

check: lint test
