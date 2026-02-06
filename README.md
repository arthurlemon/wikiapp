# Museum Visitor Analysis

Correlates annual museum attendance with city population for museums exceeding 2 million visitors, using data from Wikipedia.

## Quick Start

```bash
docker compose up --build
```

This starts 4 services:

| Service | URL | Purpose |
|---------|-----|---------|
| `postgres` | localhost:5432 | PostgreSQL database |
| `pipeline` | (runs once) | Fetches Wikipedia data, populates DB, prints regression |
| `api` | http://localhost:8000 | REST API for querying data + predictions |
| `notebook` | http://localhost:8888 | Jupyter for interactive analysis |

### API Examples

```bash
curl http://localhost:8000/museums          # list all museums
curl http://localhost:8000/regression       # model summary
curl -X POST http://localhost:8000/predict \
     -H "Content-Type: application/json" \
     -d '{"city_population": 5000000}'      # predict visitors
```

Auto-generated OpenAPI docs at http://localhost:8000/docs.

### Local Development (no Docker)

```bash
pip install -e ".[dev]"
wikiapp                      # uses SQLite by default
pytest -v                    # runs tests against SQLite in-memory
```

## Architecture

```
src/wikiapp/
├── scraper.py      # Wikipedia API → museum list (with offline fallback)
├── population.py   # City population lookup + Wikipedia API enrichment
├── db.py           # SQLAlchemy Core — PostgreSQL or SQLite via DATABASE_URL
├── model.py        # Linear regression (sklearn)
├── api.py          # FastAPI endpoints (museums, regression, predict)
└── cli.py          # Pipeline entry point
```

```
docker-compose.yml
├── postgres         PostgreSQL 16
├── pipeline         CLI → fetches data, populates DB
├── api              FastAPI (uvicorn)
└── notebook         Jupyter
```

## Design Decisions & Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **PostgreSQL in Docker** | Production-grade, supports concurrent reads from API + notebook. | Heavier than SQLite. Overkill for single-user local use, but right for a shared service. |
| **SQLAlchemy Core** | Handles PostgreSQL/SQLite dialect differences (SERIAL vs AUTOINCREMENT, ON CONFLICT) transparently. Tests run on SQLite, Docker uses PostgreSQL. | Adds a dependency. Worth it for dual-backend support without raw SQL divergence. |
| **SQLite fallback** | `pip install -e . && wikiapp` works with zero infrastructure. Tests need no database server. | Two code paths for upserts (pg_insert / sqlite_insert). Both tested via CI. |
| **FastAPI** | Async-ready, auto-generates OpenAPI docs at `/docs`, Pydantic validation, minimal boilerplate. | Slightly heavier than Flask for a 3-endpoint API. Pays off immediately via auto-docs and typing. |
| **Bundled data fallback** | Wikipedia API may be unreachable. The pipeline always works. | Snapshot goes stale. Must be updated or refreshed via the pipeline when connectivity is available. |
| **Curated population table** | Reliable, fast. Infobox scraping is fragile. | Doesn't auto-update. For production: Wikidata SPARQL or World Bank API. |
| **stdlib HTML parser** | Avoids `beautifulsoup4` dependency. Lighter image. | Less robust against HTML quirks. Acceptable for a single known page. |
| **Simple linear regression** | Explicitly requested. Easy to interpret. | Poor fit expected — city population is a weak predictor. |

## Known Limitations

- **Small sample** (~30 museums) limits statistical significance.
- **Linear model is simplistic**: log-log or polynomial features would likely fit better.
- **Confounders not modeled**: tourism infrastructure, free admission, museum reputation, GDP.
- **Cities with multiple museums** share the same X value. Valid per-museum, but city-level aggregation may be more appropriate.
- **Wikipedia table format** can change; the HTML parser targets the current layout.
- **No authentication** on the API — add API keys or OAuth for public deployment.

## Next Steps (Production Roadmap)

1. **Better data sources**: Wikidata SPARQL for structured museum metadata; World Bank / UN API for demographics.
2. **Feature engineering**: GDP per capita, international tourism arrivals, museum type, admission price.
3. **Model improvements**: log-transform, Ridge/Lasso, cross-validation, proper train/test split.
4. **Schema migrations**: Alembic for managing PostgreSQL schema changes.
5. **Async API**: switch to async SQLAlchemy + asyncpg for higher throughput.
6. **CI/CD**: GitHub Actions — lint, test, build Docker images, push to registry.
7. **Monitoring**: Prometheus metrics on the API, Sentry for error tracking.
8. **Scheduled refresh**: cron or Airflow to re-fetch Wikipedia data periodically.

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

Tests use SQLite in-memory — no PostgreSQL needed locally.
