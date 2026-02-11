# Shared base image for pipeline, API, and notebook.
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv build --wheel

FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/

# Install with api + notebook extras (covers all services)
RUN whl=$(ls /tmp/wikiapp-*.whl) && uv pip install --system --no-cache "${whl}[api,notebook]" && rm /tmp/*.whl

# Copy Alembic config (needed for migrations)
COPY alembic.ini .
COPY alembic/ alembic/

# Copy notebooks
COPY notebooks/ notebooks/

RUN mkdir -p /app/artifacts
ENTRYPOINT ["wikiapp"]
