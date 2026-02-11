"""ETL service — orchestrate museum and population data ingestion.

Coordinates between external API clients and database repositories.
No direct SQL or HTTP calls in this module.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import requests

from wikiapp.clients.wikipedia import fetch_museums
from wikiapp.clients.wikidata import get_city_population
from wikiapp.repositories import museums as museums_repo
from wikiapp.repositories import populations as populations_repo

logger = logging.getLogger(__name__)


def ingest_museums(engine=None) -> int:
    """Fetch museums from Wikipedia and persist to museums_raw."""
    rows = fetch_museums()
    if not rows:
        return 0
    museums_repo.replace_all(rows, engine)
    logger.info("Ingested %d museums into museums_raw", len(rows))
    return len(rows)


def get_distinct_city_titles(engine=None) -> list[str]:
    """Return unique city Wikipedia titles from museums_raw."""
    return museums_repo.get_distinct_city_titles(engine)


def enrich_population(city_titles: Sequence[str], engine=None) -> int:
    """Fetch population for each city from Wikidata and persist."""
    results = []
    for title in city_titles:
        if not title:
            continue
        try:
            result = get_city_population(title)
        except requests.RequestException as exc:
            logger.warning("Skipping population for %s: %s", title, exc)
            continue
        if result:
            results.append(result)

    populations_repo.replace_all(results, engine)
    logger.info("Enriched population for %d / %d cities", len(results), len(city_titles))
    return len(results)
