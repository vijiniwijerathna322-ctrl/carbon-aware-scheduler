UV ?= uv

.PHONY: lint test check docker-build docker-run
lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy src

test:
	$(UV) run pytest -q

check: lint test

docker-build:
	docker build -t carbon-scheduler:demo .

docker-run:
	docker run --rm --read-only --tmpfs /tmp --cap-drop ALL -p 127.0.0.1:8000:8000 carbon-scheduler:demo
