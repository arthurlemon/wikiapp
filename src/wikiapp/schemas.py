"""Pydantic models for API request/response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MuseumOut(BaseModel):
    museum_name: str
    city: str
    country: str | None
    annual_visitors: int
    population: int | None


class RegressionOut(BaseModel):
    equation: str
    coefficient: float
    intercept: float
    r_squared: float
    rmse: float
    mae: float
    n_samples: int
    model_version: str


class PredictRequest(BaseModel):
    population: int = Field(gt=0, description="City population")


class PredictResponse(BaseModel):
    population: int
    predicted_visitors: int
    model_version: str
