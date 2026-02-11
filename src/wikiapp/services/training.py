"""Training service — log-log linear regression with artifact persistence.

Contains ML training logic and model loading. All DB access is
delegated to repositories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy.engine import Engine

from wikiapp.config import settings
from wikiapp.db import get_session
from wikiapp.repositories import features as features_repo
from wikiapp.repositories import models as models_repo

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
    """Train a log-log linear regression and persist the artifact."""
    with get_session(engine) as session:
        df = features_repo.read_training_data(session)

    if df.empty:
        raise ValueError("No training data in museum_city_features")

    X_raw = df[["population"]].to_numpy(dtype=float)
    y_raw = df["annual_visitors"].to_numpy(dtype=float)

    # Log-log transform
    log_X = np.log(X_raw)
    log_y = np.log(y_raw)

    model = LinearRegression()
    model.fit(log_X, log_y)

    # Metrics in original space for interpretability
    y_pred = np.exp(model.predict(log_X))
    r2 = float(r2_score(y_raw, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_raw, y_pred)))
    mae = float(mean_absolute_error(y_raw, y_pred))

    # Save artifact
    version = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    artifacts_dir = Path(settings.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = str(artifacts_dir / f"log_regression_{version}.joblib")
    joblib.dump(model, artifact_path)

    # Register in DB
    models_repo.register(version, artifact_path, r2, mae, rmse, engine)

    result = TrainResult(
        model_version=version,
        artifact_path=artifact_path,
        coef=float(model.coef_[0]),
        intercept=float(model.intercept_),
        r2=r2, rmse=rmse, mae=mae,
        n_samples=len(y_raw),
    )
    logger.info("Trained model v%s: R²=%.4f RMSE=%.0f MAE=%.0f (n=%d)",
                version, r2, rmse, mae, len(y_raw))
    return result


def load_latest_model(engine: Engine | None = None) -> tuple[LinearRegression, str]:
    """Load the most recently registered model from disk."""
    meta = models_repo.get_latest(engine)
    if meta is None:
        raise ValueError("No model found in model_registry. Run training first.")
    model = joblib.load(meta["artifact_path"])
    return model, meta["model_version"]


def summary_from_db(engine: Engine | None = None) -> dict | None:
    """Return the latest model's metrics from the registry."""
    meta = models_repo.get_latest(engine)
    if meta is None:
        return None
    return {
        "model_version": meta["model_version"],
        "r2": meta["r2"],
        "mae": meta["mae"],
        "rmse": meta["rmse"],
    }
