"""Transform — join raw tables into the feature table for ML.

The museum_city_features table is the analytical layer that the model
and the API query against.  It merges museum attendance with city
population, keeping only rows that have both values.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from wikiapp.config import settings
from wikiapp.db import get_session

logger = logging.getLogger(__name__)


def build_feature_table(engine: Engine | None = None) -> int:
    """Build museum_city_features by joining museums_raw + city_population_raw."""
    with get_session(engine) as session:
        museums = pd.read_sql(
            text("""
                SELECT museum_name, city, country, annual_visitors,
                       attendance_year, city_wikipedia_title
                FROM museums_raw
            """),
            session.connection(),
        )
        population = pd.read_sql(
            text("""
                SELECT city, city_wikipedia_title, wikidata_item_id,
                       population, population_as_of
                FROM city_population_raw
            """),
            session.connection(),
        )

        if museums.empty or population.empty:
            session.execute(text("DELETE FROM museum_city_features"))
            logger.warning("Empty raw tables — feature table cleared")
            return 0

        # Filter to museums above threshold with valid visitor counts
        museums = museums[
            museums["annual_visitors"].notna()
            & (museums["annual_visitors"] >= settings.visitor_threshold)
        ].copy()

        if museums.empty:
            session.execute(text("DELETE FROM museum_city_features"))
            return 0

        # Take most recent population per city
        pop_latest = (
            population.sort_values(by=["city_wikipedia_title", "population_as_of"])
            .drop_duplicates(subset=["city_wikipedia_title"], keep="last")
        )

        merged = museums.merge(
            pop_latest,
            how="inner",
            on="city_wikipedia_title",
            suffixes=("_museum", "_pop"),
        )
        merged = merged[[
            "museum_name", "city_museum", "country",
            "annual_visitors", "attendance_year",
            "population", "population_as_of",
        ]].dropna(subset=["population", "annual_visitors"])
        merged = merged.rename(columns={"city_museum": "city"})

        session.execute(text("DELETE FROM museum_city_features"))
        for row in merged.to_dict(orient="records"):
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

    logger.info("Built feature table with %d rows", len(merged))
    return len(merged)
