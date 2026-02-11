"""Repository for the museums_raw table."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from wikiapp.db import get_session


def replace_all(rows: list[dict], engine: Engine | None = None) -> None:
    """Truncate and reload museums_raw with the given rows."""
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


def get_distinct_city_titles(engine: Engine | None = None) -> list[str]:
    """Return unique city Wikipedia titles from museums_raw."""
    with get_session(engine) as session:
        rows = session.execute(text("""
            SELECT DISTINCT COALESCE(NULLIF(city_wikipedia_title, ''), NULLIF(city, ''))
            FROM museums_raw
            WHERE COALESCE(NULLIF(city_wikipedia_title, ''), NULLIF(city, '')) IS NOT NULL
        """)).all()
    return [r[0] for r in rows if r[0]]
