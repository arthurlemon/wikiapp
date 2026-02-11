"""ETL — extract museum and population data into raw tables.

Raw tables (museums_raw, city_population_raw) follow a truncate-and-reload
pattern: each run replaces all data with the latest fetch.  This is
acceptable for a small dataset that changes infrequently.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import requests
from sqlalchemy import text
from sqlalchemy.engine import Engine

from wikiapp.clients.wikipedia import fetch_museums
from wikiapp.clients.wikidata import get_city_population
from wikiapp.db import get_session

logger = logging.getLogger(__name__)


def ingest_museums(engine: Engine | None = None) -> int:
    """Fetch museums from Wikipedia and insert into museums_raw."""
    rows = fetch_museums()
    if not rows:
        return 0

    with get_session(engine) as session:
        session.execute(text("DELETE FROM museums_raw"))
        for row in rows:
            session.execute(
                text("""
                    INSERT INTO museums_raw
                        (museum_name, city, country, annual_visitors,
                         attendance_year, city_wikipedia_title, source_url)
                    VALUES
                        (:museum_name, :city, :country, :annual_visitors,
                         :attendance_year, :city_wikipedia_title, :source_url)
                """),
                row,
            )
    logger.info("Ingested %d museums into museums_raw", len(rows))
    return len(rows)


def get_distinct_city_titles(engine: Engine | None = None) -> list[str]:
    """Return unique city Wikipedia titles from museums_raw."""
    with get_session(engine) as session:
        rows = session.execute(text("""
            SELECT DISTINCT COALESCE(NULLIF(city_wikipedia_title, ''), NULLIF(city, ''))
            FROM museums_raw
            WHERE COALESCE(NULLIF(city_wikipedia_title, ''), NULLIF(city, '')) IS NOT NULL
        """)).all()
    return [r[0] for r in rows if r[0]]


def enrich_population(city_titles: Sequence[str], engine: Engine | None = None) -> int:
    """Fetch population for each city from Wikidata (with fallback) and insert."""
    inserted = 0
    with get_session(engine) as session:
        session.execute(text("DELETE FROM city_population_raw"))
        for title in city_titles:
            if not title:
                continue
            try:
                result = get_city_population(title)
            except requests.RequestException as exc:
                logger.warning("Skipping population for %s: %s", title, exc)
                continue
            if not result:
                continue

            session.execute(
                text("""
                    INSERT INTO city_population_raw
                        (city, country, city_wikipedia_title, wikidata_item_id,
                         population, population_as_of, source_url)
                    VALUES
                        (:city, NULL, :city_wikipedia_title, :wikidata_item_id,
                         :population, :population_as_of, NULL)
                """),
                result,
            )
            inserted += 1
    logger.info("Enriched population for %d / %d cities", inserted, len(city_titles))
    return inserted
