"""Transform service — join raw tables into the feature table for ML.

Contains the pandas join/filter business logic. All DB access is
delegated to repositories.
"""

from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from wikiapp.config import settings
from wikiapp.db import get_session
from wikiapp.repositories import features as features_repo

logger = logging.getLogger(__name__)


def build_feature_table(engine: Engine | None = None) -> int:
    """Build museum_city_features by joining museums_raw + city_population_raw."""
    with get_session(engine) as session:
        museums = features_repo.read_museums_raw(session)
        population = features_repo.read_populations_raw(session)

        if museums.empty or population.empty:
            features_repo.clear(session)
            logger.warning("Empty raw tables — feature table cleared")
            return 0

        # Filter to museums above threshold with valid visitor counts
        museums = museums[
            museums["annual_visitors"].notna()
            & (museums["annual_visitors"] >= settings.visitor_threshold)
        ].copy()

        if museums.empty:
            features_repo.clear(session)
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

        features_repo.replace_all(merged.to_dict(orient="records"), session)

    logger.info("Built feature table with %d rows", len(merged))
    return len(merged)
