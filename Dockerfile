# syntax=docker/dockerfile:1
FROM python:3.11.17-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.11.17-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89 AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --no-create-home --uid 10001 --user-group app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY demo/ ./demo/
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 \
    CARBON_DATA_DIR=/app/demo/data CARBON_MODELS_DIR=/app/demo/models DEMO_MODE=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)" || exit 1
CMD ["uvicorn", "carbon_scheduler.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
