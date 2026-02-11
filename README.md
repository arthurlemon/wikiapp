# Museum Visitor Analysis

Hello dear reviewer, thank you for taking some time to look at my work !

## Overview

This is an end-to-end data pipeline that pulls museum attendance from Wikipedia and city population from Wikidata, joins them, trains a simple linear regression, and serves predictions through a REST API.

I went with a standard **bronze/silver table pattern**: raw ingested data stays untouched in `museums_raw` and `city_population_raw`, while the cleaned join lands in `museum_city_features`.

For the database layer, I went with **PostgreSQL + SQLAlchemy + Alembic** for versioned migrations.

I used **`uv`** as the package manager — it's fast. The Docker build uses `uv build --wheel` in a multi-stage setup so the final image stays slim.

The Wikipedia HTML parsing uses **BeautifulSoup** since the table format varies enough that regex would be fragile. Both API clients have **offline fallbacks** (a bundled JSON snapshot for museums, a curated lookup dict for populations) so the pipeline always produces results even if apis are not returning results.

I added a simple **Prefect orchestration as optional** mostly as illustrative purposes on one way to deploy and schedule the pipelines.

Finally I added a minimal **FastAPI** layer, again mostly for illustrative purposes on how we could serve the model.

## Reproducing results

### Option 1. Docker

```bash
docker compose up --build
```

| Service | URL | Purpose |
|---------|-----|---------|
| `postgres` | localhost:5432 | PostgreSQL 16 |
| `pipeline` | (runs once) | ETL + feature build + model training |
| `api` | <http://localhost:8000> | REST API (OpenAPI docs at /docs) |
| `notebook` | <http://localhost:8888> | Jupyter notebook |

### With Prefect orchestration (optional)

```bash
pip install -e ".[orchestration]"
wikiapp run-all --orchestrate
```

## API

```bash
curl http://localhost:8000/museums          # list museums + city population
curl http://localhost:8000/regression       # model summary (R², RMSE, equation)
curl -X POST http://localhost:8000/predict \
     -H "Content-Type: application/json" \
     -d '{"population": 5000000}'           # predict visitors
```

## Architecture

```
src/wikiapp/
├── config.py           # Settings from env vars (DATABASE_URL, etc.)
├── clients/
│   ├── wikipedia.py    # Wikipedia API → museum list (BS4 + bundled fallback)
│   └── wikidata.py     # Wikidata P1082 → city population (+ curated fallback)
├── db.py               # SQLAlchemy engine, sessions, Alembic migrations
├── etl.py              # Ingest museums + enrich population → raw tables
├── transform.py        # Join raw tables → museum_city_features
├── train.py            # Train, persist (joblib), register in model_registry
├── pipelines.py        # Optional Prefect flows
├── api.py              # FastAPI (museums, regression, predict)
├── schemas.py          # Pydantic request/response models
└── cli.py              # CLI with subcommands + --orchestrate flag
```

### Data flow

```
Wikipedia API → museums_raw (bronze)
Wikidata API  → city_population_raw (bronze)
                    ↓ join + filter (>2M visitors)
              museum_city_features (silver)
                    ↓ train
              model_registry + joblib artifact
                    ↓ serve
              FastAPI /predict
```

### Database schema (4 tables)

- **museums_raw** — raw museum data from Wikipedia (name, city, visitors, year)
- **city_population_raw** — population from Wikidata (city, population, as_of date)
- **museum_city_features** — joined analytical table for ML
- **model_registry** — versioned model metadata (R², RMSE, MAE, artifact path)

Managed by Alembic migrations.

## Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **PostgreSQL only** | Single backend simplifies upsert logic, migrations, and deployment | Requires Docker or a PG instance for all environments |
| **Alembic migrations** | Versioned, replayable schema changes | Extra file overhead vs. plain create_all |
| **Wikidata P1082 for population** | Structured, auto-updating, the canonical source | API may be slow/unreachable; curated lookup as fallback |
| **Bundled data fallback** | Pipeline always works offline (CI, air-gapped) | Snapshot goes stale; refreshed when API is reachable |
| **Bronze/silver table pattern** | Clean data lineage; raw tables preserved for reprocessing | More tables than a single normalized schema |
| **Model registry + joblib** | Versioned models, metrics tracked, easy rollback | Adds filesystem dependency; production would use S3/GCS |
| **Prefect optional** | Adds observability/scheduling when needed, zero overhead when not | Extra dependency (200+ MB); only installed with `[orchestration]` |
| **FastAPI** | Auto OpenAPI docs, Pydantic validation, async-ready | Heavier than Flask for 3 endpoints; pays off via /docs |
| **BeautifulSoup** | More robust HTML parsing than stdlib html.parser | Extra dependency; justified by table format variability |
| **>2M visitor threshold** | Matches the task specification exactly | Applied during both ingestion and feature building |

## Known Limitations

- **Small sample** (~33 museums) limits statistical significance
- **Linear model is simplistic** — log-log or polynomial features would fit better
- **Confounders not modeled** — tourism infrastructure, free admission, GDP, reputation
- **Cities with multiple museums** share the same X value (valid per-museum, but city-level aggregation may be more appropriate)
- **Wikipedia table format** can change; parser needs maintenance
- **No API authentication** — add API keys or OAuth for public deployment
- **Truncate-and-reload ETL** — acceptable for this dataset size; production would use incremental loads

## Production Roadmap

1. **Feature engineering** — GDP, tourism arrivals, museum type, admission price, log transforms
2. **Model improvements** — Ridge/Lasso, cross-validation, proper train/test split
3. **Async API** — switch to async SQLAlchemy + asyncpg for throughput
4. **CI/CD** — GitHub Actions: lint, test, build Docker, push to registry
5. **Monitoring** — Prometheus metrics, Sentry error tracking
6. **Model serving** — separate model service, A/B testing, canary deploys
7. **Data quality** — Great Expectations or similar for pipeline validation

## Testing

```bash
python -m pytest -v
```

Tests cover the Wikipedia/Wikidata clients and data parsing — no database connection needed.
