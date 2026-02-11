"""Repository for the model_registry table."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from wikiapp.db import get_session


def register(
    version: str,
    path: str,
    r2: float,
    mae: float,
    rmse: float,
    engine: Engine | None = None,
) -> None:
    """Insert a new model version into the registry."""
    with get_session(engine) as session:
        session.execute(
            text("""
                INSERT INTO model_registry (model_version, artifact_path, r2, mae, rmse)
                VALUES (:v, :p, :r2, :mae, :rmse)
            """),
            {"v": version, "p": path, "r2": r2, "mae": mae, "rmse": rmse},
        )


def get_latest(engine: Engine | None = None) -> dict | None:
    """Return the latest model entry (version, path, metrics), or None."""
    with get_session(engine) as session:
        row = session.execute(
            text("""
                SELECT model_version, artifact_path, r2, mae, rmse
                FROM model_registry
                ORDER BY created_at DESC
                LIMIT 1
            """)
        ).first()
    if row is None:
        return None
    return {
        "model_version": row.model_version,
        "artifact_path": row.artifact_path,
        "r2": row.r2,
        "mae": row.mae,
        "rmse": row.rmse,
    }
