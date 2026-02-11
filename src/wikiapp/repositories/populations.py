"""Repository for the city_population_raw table."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from wikiapp.db import get_session


def replace_all(results: list[dict], engine: Engine | None = None) -> None:
    """Truncate and reload city_population_raw with the given rows."""
    with get_session(engine) as session:
        session.execute(text("DELETE FROM city_population_raw"))
        for result in results:
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
