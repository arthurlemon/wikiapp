"""FastAPI service exposing museum data and regression results.

Endpoints:
  GET  /health      — liveness check
  GET  /museums     — list all museums with city population
  GET  /regression  — latest model summary from registry
  POST /predict     — predict visitors for a given city population
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from wikiapp.db import get_engine, get_session
from wikiapp.train import load_latest_model, summary_from_db
from wikiapp.schemas import MuseumOut, PredictRequest, PredictResponse, RegressionOut

app = FastAPI(title="Museum Visitor Analysis API", version="0.3.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/museums", response_model=list[MuseumOut])
def list_museums():
    """Return all museums in the feature table."""
    engine = get_engine()
    with get_session(engine) as session:
        df = pd.read_sql(
            text("""
                SELECT museum_name, city, country, annual_visitors, population
                FROM museum_city_features
                ORDER BY annual_visitors DESC
            """),
            session.connection(),
        )
    if df.empty:
        raise HTTPException(404, "No data. Run the pipeline first.")
    return df.to_dict(orient="records")


@app.get("/regression", response_model=RegressionOut)
def regression():
    """Return the latest regression model summary."""
    engine = get_engine()
    summary = summary_from_db(engine)
    if not summary:
        raise HTTPException(404, "No model found. Run training first.")

    model, version = load_latest_model(engine)
    coef = float(model.coef_[0])
    intercept = float(model.intercept_)

    with get_session(engine) as session:
        n = session.execute(
            text("SELECT COUNT(*) FROM museum_city_features")
        ).scalar()

    return RegressionOut(
        equation=f"log(visitors) = {coef:.4f} * log(population) + {intercept:.4f}",
        coefficient=coef,
        intercept=intercept,
        r_squared=summary["r2"],
        rmse=summary["rmse"],
        mae=summary["mae"],
        n_samples=n,
        model_version=version,
    )


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Predict museum visitors given a city population."""
    engine = get_engine()
    try:
        model, version = load_latest_model(engine)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc

    log_pred = model.predict(np.array([[np.log(req.population)]], dtype=float))[0]
    predicted = np.exp(log_pred)
    return PredictResponse(
        population=req.population,
        predicted_visitors=max(0, int(predicted)),
        model_version=version,
    )
