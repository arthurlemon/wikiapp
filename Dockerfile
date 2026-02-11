# Shared base image for pipeline, API, and notebook.
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/

# Install with postgres + api extras (covers all services)
RUN pip install --no-cache-dir "/tmp/wikiapp-*.whl[api]" && rm /tmp/*.whl

# Copy Alembic config (needed for migrations)
COPY alembic.ini .
COPY alembic/ alembic/

# Copy notebooks
COPY notebooks/ notebooks/

RUN mkdir -p /app/artifacts
ENTRYPOINT ["wikiapp"]
