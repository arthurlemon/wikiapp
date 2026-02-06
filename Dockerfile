# Multi-stage build: keeps final image small.
# Stage 1: build the wheel
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir build && python -m build --wheel

# Stage 2: runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
# Pre-create data dir for SQLite
RUN mkdir -p /app/data
ENTRYPOINT ["wikiapp"]
