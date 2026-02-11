---
jupyter:
  jupytext:
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.19.1
  kernelspec:
    display_name: wikiapp
    language: python
    name: python3
---

# Museum Attendance vs City Population

This notebook reads the `museum_city_features` table (populated by the pipeline)
and visualises the log-log regression model (power-law fit).

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import text

from wikiapp.db import get_engine, get_session
from wikiapp.services.training import load_latest_model, summary_from_db

sns.set_theme(style="whitegrid")
engine = get_engine()
```

## 1. Load Data

```python
with get_session(engine) as session:
    df = pd.read_sql(
        text("SELECT museum_name, city, country, annual_visitors, population FROM museum_city_features"),
        session.connection(),
    )
print(f"{len(df)} museums in feature table")
df.head(10)
```

## 2. Distributions

```python
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].hist(df["annual_visitors"] / 1e6, bins=12, edgecolor="black", alpha=0.7)
axes[0].set_xlabel("Annual Visitors (millions)")
axes[0].set_ylabel("Count")
axes[0].set_title("Distribution of Museum Visitors")

axes[1].hist(df["population"] / 1e6, bins=12, edgecolor="black", alpha=0.7, color="orange")
axes[1].set_xlabel("City Population (millions)")
axes[1].set_ylabel("Count")
axes[1].set_title("Distribution of City Populations")

plt.tight_layout()
plt.show()
```

## 3. Regression

```python
model, version = load_latest_model(engine)
metrics = summary_from_db(engine)
print(f"Model version: {version}")
print(f"R² = {metrics['r2']:.4f}  |  RMSE = {metrics['rmse']:,.0f}  |  MAE = {metrics['mae']:,.0f}")
coef, intercept = float(model.coef_[0]), float(model.intercept_)
print(f"log(visitors) = {coef:.4f} * log(population) + {intercept:.4f}")
print(f"  → visitors = e^{intercept:.4f} × population^{coef:.4f}")
```

```python
fig, ax = plt.subplots(figsize=(10, 7))

ax.scatter(df["population"] / 1e6, df["annual_visitors"] / 1e6,
           s=80, alpha=0.7, edgecolors="black", linewidths=0.5, zorder=5)

for _, row in df.iterrows():
    ax.annotate(row["museum_name"],
                (row["population"] / 1e6, row["annual_visitors"] / 1e6),
                fontsize=7, alpha=0.8, xytext=(5, 5), textcoords="offset points")

# Log-log regression curve in original space
x_range = np.linspace(df["population"].min(), df["population"].max(), 200)
y_range = np.exp(model.predict(np.log(x_range).reshape(-1, 1)))
ax.plot(x_range / 1e6, y_range / 1e6, color="red", linewidth=2,
        label=f"log-log: visitors = e^{intercept:.2f} × pop^{coef:.2f}\nR² = {metrics['r2']:.4f}")

ax.set_xlabel("City Population (millions)", fontsize=12)
ax.set_ylabel("Annual Museum Visitors (millions)", fontsize=12)
ax.set_title("Museum Visitors vs City Population — Log-Log Regression", fontsize=14)
ax.legend(fontsize=11)
plt.tight_layout()
plt.show()
```

## 4. Residual Analysis

```python
df["predicted"] = np.exp(model.predict(np.log(df[["population"]].to_numpy(dtype=float))))
df["residual"] = df["annual_visitors"] - df["predicted"]

fig, ax = plt.subplots(figsize=(10, 5))
colors = ["green" if r > 0 else "red" for r in df["residual"]]
ax.barh(df["museum_name"], df["residual"] / 1e6, color=colors, alpha=0.7)
ax.set_xlabel("Residual (millions of visitors)")
ax.set_title("Residuals: Actual − Predicted Visitors")
ax.axvline(0, color="black", linewidth=0.8)
plt.tight_layout()
plt.show()
```

## Interpretation

- **Log-log model**: `log(visitors) = coef × log(population) + intercept` captures a power-law relationship, which is a better fit for this kind of data than a plain linear model but poor performance due to lack of correlation between x & y.
- **Positive residuals** (green): museums that outperform their city population prediction, driven by international tourism, free admission, or iconic status.
- **Negative residuals** (red): museums below prediction — possibly in cities with many competing museums or less international draw.

### Potential Next Steps
- Add features (GDP, tourism arrivals, museum type, free-admission flag)
- Aggregate museums by city for a city-level analysis
- Use cross-validation with a larger dataset
