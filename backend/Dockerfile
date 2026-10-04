# syntax=docker/dockerfile:1
# Build context is the REPO ROOT (so the committed data/snapshot/ is baked in):
#   docker build -f backend/Dockerfile .
# backend/Dockerfile.dockerignore limits what is sent to the daemon.

# ---- build stage: resolve and install deps with uv ----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first for better layer caching.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the project itself.
COPY backend/README.md ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---- runtime stage ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    SNAPSHOT_PATH=/app/data/snapshot/atlas-snapshot.json

RUN groupadd --system --gid 10001 atlas \
    && useradd --system --uid 10001 --gid atlas --no-create-home --shell /usr/sbin/nologin atlas

WORKDIR /app
COPY --from=builder --chown=atlas:atlas /app/.venv /app/.venv
# Read-only graph snapshot, loaded once at startup (atlas.graph.store).
COPY --chown=atlas:atlas data/snapshot /app/data/snapshot
# Committed OpenAI caches (embeddings, explanations), so the deployed demo needs no live calls.
COPY --chown=atlas:atlas data/cache /app/data/cache

USER atlas

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)" || exit 1

CMD ["sh", "-c", "exec uvicorn atlas.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
