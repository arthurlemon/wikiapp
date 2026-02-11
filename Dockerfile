# syntax=docker/dockerfile:1.7

# Build the project wheel once.
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv build --wheel

FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# lxml needs libxml2 and libxslt at runtime
RUN apt-get update && apt-get install -y --no-install-recommends libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Install deps from the lockfile first (best cache hit and reproducibility).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --format requirements-txt --all-extras --no-dev --no-emit-project -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# Then install the built wheel without resolving deps again.
COPY --from=builder /build/dist/*.whl /tmp/
RUN uv pip install --system --no-cache --no-deps /tmp/wikiapp-*.whl \
    && rm -f /tmp/*.whl

# Copy Alembic config (needed for migrations)
COPY alembic.ini .
COPY alembic/ alembic/

# Copy notebooks
COPY notebooks/ notebooks/

RUN mkdir -p /app/artifacts
ENTRYPOINT ["wikiapp"]
