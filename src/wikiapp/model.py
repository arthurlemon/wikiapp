"""Linear regression: city population → museum visitors.

Model choice rationale:
- The task explicitly asks for a linear regression, so we use sklearn's
  LinearRegression. This is appropriate for an MVP / exploratory analysis.
- We also compute R², MAE, and RMSE to quantify fit quality.
- The model operates on per-museum rows: each museum is one sample with
  (city_population) as X and (visitors) as y.

Known limitations:
- Linear regression assumes a linear relationship; in reality the
  relationship is likely sublinear (log-log may fit better).
- Cities with multiple major museums (London, Paris, D.C.) contribute
  several points with the same X value — this doesn't violate OLS
  assumptions but may inflate the apparent correlation.
- Sample size is small (~30 museums), limiting statistical power.
- Confounders (tourism infrastructure, museum reputation, free admission)
  are not modeled.

Next steps for a production system:
- Try log-transformed features, polynomial regression, or regularized models.
- Add features: GDP, tourism spend, free-admission flag, museum age.
- Use cross-validation instead of a single train/test split.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


@dataclass
class RegressionResult:
    """Container for regression outputs."""

    model: LinearRegression
    coef: float
    intercept: float
    r2: float
    rmse: float
    mae: float
    X: np.ndarray
    y: np.ndarray
    y_pred: np.ndarray


def run_regression(df: pd.DataFrame) -> RegressionResult:
    """Fit a simple linear regression: city_population → visitors.

    Args:
        df: DataFrame with columns 'city_population' and 'visitors'.

    Returns:
        RegressionResult with model and metrics.
    """
    X = df[["city_population"]].values
    y = df["visitors"].values

    model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)

    return RegressionResult(
        model=model,
        coef=float(model.coef_[0]),
        intercept=float(model.intercept_),
        r2=float(r2_score(y, y_pred)),
        rmse=float(np.sqrt(mean_squared_error(y, y_pred))),
        mae=float(mean_absolute_error(y, y_pred)),
        X=X,
        y=y,
        y_pred=y_pred,
    )


def summary(result: RegressionResult) -> str:
    """Human-readable summary of regression results."""
    return (
        f"Linear Regression: visitors = {result.coef:.4f} * city_population + {result.intercept:.0f}\n"
        f"  R²   = {result.r2:.4f}\n"
        f"  RMSE = {result.rmse:,.0f}\n"
        f"  MAE  = {result.mae:,.0f}\n"
        f"  n    = {len(result.y)}"
    )
