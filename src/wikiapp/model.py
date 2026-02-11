"""Linear regression with artifact persistence and model registry.

Each training run:
1. Reads the feature table.
2. Fits a LinearRegression (population → visitors).
3. Saves the model as a joblib artifact.
4. Records version + metrics in the model_registry table.

The API loads the latest registered model for serving predictions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy import text
from sqlalchemy.engine import Engine

from wikiapp.config import settings
from wikiapp.db import get_session

logger = logging.getLogger(__name__)


@dataclass
class TrainResult:
    model_version: str
    artifact_path: str
    coef: float
    intercept: float
    r2: float
    rmse: float
    mae: float
    n_samples: int


def train(engine: Engine | None = None) -> TrainResult:
    """Train a linear regression and persist the artifact."""
    with get_session(engine) as session:
        df = pd.read_sql(
            text("SELECT population, annual_visitors FROM museum_city_features"),
            session.connection(),
        )

    if df.empty:
        raise ValueError("No training data in museum_city_features")

    X = df[["population"]].to_numpy(dtype=float)
    y = df["annual_visitors"].to_numpy(dtype=float)

    model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)

    r2 = float(r2_score(y, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y, y_pred)))
    mae = float(mean_absolute_error(y, y_pred))

    # Save artifact
    version = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    artifacts_dir = Path(settings.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = str(artifacts_dir / f"linear_regression_{version}.joblib")
    joblib.dump(model, artifact_path)

    # Register in DB
    with get_session(engine) as session:
        session.execute(
            text("""
                INSERT INTO model_registry (model_version, artifact_path, r2, mae, rmse)
                VALUES (:v, :p, :r2, :mae, :rmse)
            """),
            {"v": version, "p": artifact_path, "r2": r2, "mae": mae, "rmse": rmse},
        )

    result = TrainResult(
        model_version=version,
        artifact_path=artifact_path,
        coef=float(model.coef_[0]),
        intercept=float(model.intercept_),
        r2=r2, rmse=rmse, mae=mae,
        n_samples=len(y),
    )
    logger.info("Trained model v%s: R²=%.4f RMSE=%.0f MAE=%.0f (n=%d)",
                version, r2, rmse, mae, len(y))
    return result


def load_latest_model(engine: Engine | None = None) -> tuple[LinearRegression, str]:
    """Load the most recently registered model from disk."""
    with get_session(engine) as session:
        row = session.execute(
            text("""
                SELECT model_version, artifact_path
                FROM model_registry
                ORDER BY created_at DESC
                LIMIT 1
            """)
        ).first()

    if row is None:
        raise ValueError("No model found in model_registry. Run training first.")

    model = joblib.load(row.artifact_path)
    return model, row.model_version


def summary_from_db(engine: Engine | None = None) -> dict | None:
    """Return the latest model's metrics from the registry."""
    with get_session(engine) as session:
        row = session.execute(
            text("""
                SELECT model_version, r2, mae, rmse
                FROM model_registry
                ORDER BY created_at DESC
                LIMIT 1
            """)
        ).first()
    if row is None:
        return None
    return {
        "model_version": row.model_version,
        "r2": row.r2,
        "mae": row.mae,
        "rmse": row.rmse,
    }
