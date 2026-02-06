"""Tests for the core pipeline: scraper → population → db → model."""

import sqlite3

import pandas as pd

from wikiapp import db, model, population, scraper


def test_bundled_snapshot_has_enough_museums():
    museums = scraper._bundled_snapshot()
    assert len(museums) >= 20
    for m in museums:
        assert m["visitors"] >= scraper.VISITOR_THRESHOLD


def test_parse_visitor_count():
    assert scraper._parse_visitor_count("10,000,000") == 10_000_000
    assert scraper._parse_visitor_count("3.5 million") == 3_500_000
    assert scraper._parse_visitor_count("") is None


def test_population_lookup():
    assert population.get_city_population("Paris") == 2_161_000
    assert population.get_city_population("London") == 8_982_000
    assert population.get_city_population("Nonexistent City XYZ") is None


def test_enrich_museums():
    museums = [{"name": "Test", "city": "Paris", "country": "France", "visitors": 5_000_000}]
    enriched = population.enrich_museums_with_population(museums)
    assert enriched[0]["city_population"] == 2_161_000


def test_db_roundtrip():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)

    museums_data = [
        {"name": "Museum A", "city": "Paris", "country": "France",
         "visitors": 5_000_000, "city_population": 2_161_000},
        {"name": "Museum B", "city": "London", "country": "UK",
         "visitors": 3_000_000, "city_population": 8_982_000},
    ]
    db.load_museums(museums_data, conn)

    df = db.query_dataset(conn)
    assert len(df) == 2
    assert "city_population" in df.columns
    conn.close()


def test_regression():
    df = pd.DataFrame({
        "city_population": [1_000_000, 5_000_000, 10_000_000, 20_000_000],
        "visitors": [2_000_000, 3_000_000, 4_000_000, 5_000_000],
    })
    result = model.run_regression(df)
    assert result.r2 > 0.9  # strong linear relationship in synthetic data
    assert result.coef > 0
    assert len(result.y_pred) == 4


def test_full_pipeline_in_memory():
    """End-to-end: snapshot → enrich → db → regression."""
    museums = scraper._bundled_snapshot()
    museums = population.enrich_museums_with_population(museums)

    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    db.load_museums(museums, conn)
    df = db.query_dataset(conn)
    conn.close()

    assert len(df) > 15
    result = model.run_regression(df)
    assert result.r2 is not None
    summary = model.summary(result)
    assert "R²" in summary
