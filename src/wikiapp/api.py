"""FastAPI service exposing museum data and regression results.

Endpoints:
  GET /health           — liveness check
  GET /museums          — list all museums with city population
  GET /regression       — regression summary + coefficients
  POST /predict         — predict visitors for a given city population

Design rationale:
- Thin read-only API over the shared PostgreSQL database.
- No authentication for the MVP; add API keys or OAuth in production.
- Pydantic models for request/response validation.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from wikiapp import db, model

app = FastAPI(title="Museum Visitor Analysis API", version="0.1.0")

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = db.get_engine()
    return _engine


# --- Schemas ---


class MuseumOut(BaseModel):
    museum: str
    city: str
    country: str
    visitors: int
    city_population: int


class RegressionOut(BaseModel):
    equation: str
    coefficient: float
    intercept: float
    r_squared: float
    rmse: float
    mae: float
    n_samples: int


class PredictRequest(BaseModel):
    city_population: int


class PredictResponse(BaseModel):
    city_population: int
    predicted_visitors: int


# --- Endpoints ---


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/museums", response_model=list[MuseumOut])
def list_museums():
    """Return all museums with city population data."""
    engine = _get_engine()
    df = db.query_dataset(engine)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data. Run the pipeline first.")
    return df.to_dict(orient="records")


@app.get("/regression", response_model=RegressionOut)
def regression():
    """Return regression model summary."""
    engine = _get_engine()
    df = db.query_dataset(engine)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data. Run the pipeline first.")
    result = model.run_regression(df)
    return RegressionOut(
        equation=f"visitors = {result.coef:.4f} * city_population + {result.intercept:.0f}",
        coefficient=result.coef,
        intercept=result.intercept,
        r_squared=result.r2,
        rmse=result.rmse,
        mae=result.mae,
        n_samples=len(result.y),
    )


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Predict museum visitors given a city population."""
    engine = _get_engine()
    df = db.query_dataset(engine)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data. Run the pipeline first.")
    result = model.run_regression(df)
    predicted = result.model.predict([[req.city_population]])[0]
    return PredictResponse(
        city_population=req.city_population,
        predicted_visitors=max(0, int(predicted)),
    )
