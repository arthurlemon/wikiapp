"""Repository for the museum_city_features table."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from wikiapp.db import get_session


def read_museums_raw(session) -> pd.DataFrame:
    """Read all rows from museums_raw."""
    return pd.read_sql(
        text("""
            SELECT museum_name, city, country, annual_visitors,
                   attendance_year, city_wikipedia_title
            FROM museums_raw
        """),
        session.connection(),
    )


def read_populations_raw(session) -> pd.DataFrame:
    """Read all rows from city_population_raw."""
    return pd.read_sql(
        text("""
            SELECT city, city_wikipedia_title, wikidata_item_id,
                   population, population_as_of
            FROM city_population_raw
        """),
        session.connection(),
    )


def replace_all(rows: list[dict], session) -> None:
    """Truncate and reload museum_city_features."""
    session.execute(text("DELETE FROM museum_city_features"))
    for row in rows:
        session.execute(
            text("""
                INSERT INTO museum_city_features
                    (museum_name, city, country, annual_visitors,
                     attendance_year, population, population_as_of)
                VALUES
                    (:museum_name, :city, :country, :annual_visitors,
                     :attendance_year, :population, :population_as_of)
            """),
            row,
        )


def clear(session) -> None:
    """Delete all rows from museum_city_features."""
    session.execute(text("DELETE FROM museum_city_features"))


def read_all(engine: Engine | None = None) -> pd.DataFrame:
    """Return all features ordered by visitors (for API)."""
    with get_session(engine) as session:
        return pd.read_sql(
            text("""
                SELECT museum_name, city, country, annual_visitors, population
                FROM museum_city_features
                ORDER BY annual_visitors DESC
            """),
            session.connection(),
        )


def read_training_data(session) -> pd.DataFrame:
    """Read population and visitor columns for model training."""
    return pd.read_sql(
        text("SELECT population, annual_visitors FROM museum_city_features"),
        session.connection(),
    )


def count(engine: Engine | None = None) -> int:
    """Return the number of rows in museum_city_features."""
    with get_session(engine) as session:
        return session.execute(
            text("SELECT COUNT(*) FROM museum_city_features")
        ).scalar()
