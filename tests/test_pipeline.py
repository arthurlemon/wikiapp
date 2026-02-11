"""End-to-end tests using SQLite in-memory — no PostgreSQL needed."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text

from wikiapp import db
from wikiapp.clients.wikipedia import _bundled_snapshot, fetch_museums, parse_museums_from_html
from wikiapp.clients.wikidata import get_city_population, _CURATED_POPULATION
from wikiapp.config import settings


def _engine():
    e = create_engine("sqlite://")
    db.init_db_tables(e)
    return e


# ---- Wikipedia client ----

def test_bundled_snapshot_has_enough_museums():
    museums = _bundled_snapshot()
    assert len(museums) >= 20
    for m in museums:
        assert m["annual_visitors"] >= settings.visitor_threshold


def test_fetch_museums_applies_threshold():
    """fetch_museums should filter below threshold (uses fallback here)."""
    museums = fetch_museums(threshold=5_000_000)
    assert all(m["annual_visitors"] >= 5_000_000 for m in museums)


SAMPLE_HTML = """
<table class='wikitable'>
  <tr><th>Museum</th><th>City</th><th>Country</th><th>Visitors</th><th>Year</th></tr>
  <tr>
    <td>Louvre</td>
    <td><a href='/wiki/Paris'>Paris</a></td>
    <td>France</td>
    <td>8,900,000</td>
    <td>2024</td>
  </tr>
  <tr>
    <td>Old Museum</td>
    <td><a href='/wiki/Berlin'>Berlin</a></td>
    <td>Germany</td>
    <td>2,100,000</td>
    <td>2023</td>
  </tr>
</table>
"""


def test_parse_museums_from_html():
    rows = parse_museums_from_html(SAMPLE_HTML)
    assert len(rows) == 2
    assert rows[0]["museum_name"] == "Louvre"
    assert rows[0]["annual_visitors"] == 8_900_000
    assert rows[0]["city_wikipedia_title"] == "Paris"


# ---- Wikidata / population client ----

def test_curated_population_fallback():
    """Curated lookup should return data for known cities."""
    result = get_city_population("Paris")
    assert result is not None
    assert result["population"] == _CURATED_POPULATION["Paris"]


def test_unknown_city_returns_none():
    result = get_city_population("Nonexistent_Place_XYZ")
    assert result is None


# ---- Database ----

def test_db_tables_created():
    e = _engine()
    with e.connect() as conn:
        tables = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )).fetchall()
    names = {r[0] for r in tables}
    assert "museums_raw" in names
    assert "city_population_raw" in names
    assert "museum_city_features" in names
    assert "model_registry" in names
    e.dispose()


# ---- ETL + Transform + Train (integration) ----

def test_full_pipeline_sqlite():
    """End-to-end: ingest → enrich → transform → train on SQLite."""
    e = _engine()

    # Simulate ingest: insert bundled snapshot into museums_raw
    museums = _bundled_snapshot()
    with db.get_session(e) as session:
        for m in museums:
            session.execute(text("""
                INSERT INTO museums_raw
                    (museum_name, city, country, annual_visitors,
                     attendance_year, city_wikipedia_title, source_url)
                VALUES
                    (:museum_name, :city, :country, :annual_visitors,
                     :attendance_year, :city_wikipedia_title, :source_url)
            """), m)

    # Simulate population enrichment using curated data
    with db.get_session(e) as session:
        for title, pop in _CURATED_POPULATION.items():
            session.execute(text("""
                INSERT INTO city_population_raw
                    (city, city_wikipedia_title, population)
                VALUES (:city, :title, :pop)
            """), {"city": title.replace("_", " "), "title": title, "pop": pop})

    # Build features
    from wikiapp.transform import build_feature_table
    n = build_feature_table(e)
    assert n > 15

    # Verify feature table
    with db.get_session(e) as session:
        df = pd.read_sql(
            text("SELECT * FROM museum_city_features"), session.connection()
        )
    assert len(df) > 15
    assert "population" in df.columns
    assert "annual_visitors" in df.columns

    # Train model
    from wikiapp.model import train, load_latest_model
    result = train(e)
    assert result.r2 is not None
    assert result.n_samples > 15

    # Load model back
    model, version = load_latest_model(e)
    assert version == result.model_version
    pred = model.predict([[10_000_000]])
    assert pred[0] > 0

    e.dispose()
