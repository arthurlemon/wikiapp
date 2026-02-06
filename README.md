# Museum Visitor Analysis

Correlates annual museum attendance with city population for museums exceeding 2 million visitors, using data from Wikipedia.

## Quick Start

```bash
# Build and run the full pipeline + notebook
docker compose up --build

# Pipeline prints regression summary, then Jupyter starts at http://localhost:8888
```

Or run locally without Docker:

```bash
pip install -e ".[notebook]"
wikiapp                      # runs pipeline, prints regression summary
jupyter notebook notebooks/  # interactive analysis
```

## Architecture

```
src/wikiapp/
├── scraper.py      # Wikipedia API → museum list (with offline fallback)
├── population.py   # City population lookup + Wikipedia API enrichment
├── db.py           # SQLite storage layer (normalized: cities + museums)
├── model.py        # Linear regression (sklearn)
└── cli.py          # Entry point
```

**Docker Compose** runs two services:
1. `pipeline` — CLI that fetches data, builds the DB, runs regression
2. `notebook` — Jupyter server for visual exploration (starts after pipeline)

Both share a volume (`appdata`) for the SQLite database.

## Design Decisions & Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **SQLite** | Zero-config, perfect for MVP. Single file, no daemon. | Not suitable for concurrent writes at scale. Migration path: swap to PostgreSQL via SQLAlchemy. |
| **Bundled data fallback** | Wikipedia API may be unreachable (CI, firewalls, rate limits). The pipeline always works. | Snapshot goes stale. Must be updated manually or via a scheduled refresh job. |
| **Curated population lookup** | City population rarely changes. Scraping Wikipedia infoboxes is fragile. | Doesn't auto-update. For production: use Wikidata SPARQL or World Bank API. |
| **stdlib HTML parser** | Avoids `beautifulsoup4` dependency. Lighter image. | Less robust against HTML quirks. Acceptable for a single known page. |
| **Simple linear regression** | Explicitly requested. Easy to interpret for stakeholders. | Poor fit expected — city population is a weak predictor of museum attendance. |
| **No ORM** | Raw SQL keeps the dependency tree small and the code transparent. | Less ergonomic for complex queries. Swap to SQLAlchemy when schema grows. |

## Known Limitations

- **Small sample size** (~30 museums) limits statistical significance.
- **Linear model is simplistic**: the relationship is likely sublinear. Log-log or polynomial features would fit better.
- **Confounders not modeled**: tourism infrastructure, free admission, museum reputation, GDP.
- **Cities with multiple museums** contribute repeated X values (same population). This is valid for per-museum analysis but a city-level aggregation may be more appropriate.
- **Wikipedia table format** can change without notice; the HTML parser targets the current layout.

## Next Steps (Production Roadmap)

1. **Better data sources**: Wikidata SPARQL for structured museum metadata; World Bank / UN API for demographics.
2. **Feature engineering**: add GDP per capita, international tourism arrivals, museum type, admission price.
3. **Model improvements**: log-transform, Ridge/Lasso, cross-validation, train/test split.
4. **API layer**: expose a FastAPI service for querying the database and running predictions.
5. **Scheduled refresh**: cron/Airflow job to re-fetch Wikipedia data periodically.
6. **PostgreSQL + migrations**: swap SQLite when multi-user access is needed.
7. **CI/CD**: GitHub Actions with the test suite, Docker image push to registry.

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```
