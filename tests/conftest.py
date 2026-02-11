"""Shared test fixtures — mock data for Wikipedia and Wikidata clients."""

from __future__ import annotations

import pytest

from wikiapp.clients.wikipedia import SOURCE_URL


MOCK_MUSEUMS = [
    {"museum_name": "Louvre", "city": "Paris", "country": "France", "annual_visitors": 8_900_000, "attendance_year": 2024, "city_wikipedia_title": "Paris", "source_url": SOURCE_URL},
    {"museum_name": "British Museum", "city": "London", "country": "United Kingdom", "annual_visitors": 5_820_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
    {"museum_name": "The Metropolitan Museum of Art", "city": "New York City", "country": "United States", "annual_visitors": 5_360_000, "attendance_year": 2024, "city_wikipedia_title": "New_York_City", "source_url": SOURCE_URL},
    {"museum_name": "Rijksmuseum", "city": "Amsterdam", "country": "Netherlands", "annual_visitors": 2_700_000, "attendance_year": 2024, "city_wikipedia_title": "Amsterdam", "source_url": SOURCE_URL},
    {"museum_name": "Small Museum", "city": "Rome", "country": "Italy", "annual_visitors": 500_000, "attendance_year": 2024, "city_wikipedia_title": "Rome", "source_url": SOURCE_URL},
]

MOCK_POPULATIONS = {
    "Paris": {"city": "Paris", "wikidata_item_id": "Q90", "population": 2_161_000, "population_as_of": None, "city_wikipedia_title": "Paris"},
    "London": {"city": "London", "wikidata_item_id": "Q84", "population": 8_982_000, "population_as_of": None, "city_wikipedia_title": "London"},
    "New_York_City": {"city": "New York City", "wikidata_item_id": "Q60", "population": 8_336_000, "population_as_of": None, "city_wikipedia_title": "New_York_City"},
    "Amsterdam": {"city": "Amsterdam", "wikidata_item_id": "Q727", "population": 905_000, "population_as_of": None, "city_wikipedia_title": "Amsterdam"},
}


@pytest.fixture()
def mock_museums():
    """Sample museum data for tests."""
    return [m.copy() for m in MOCK_MUSEUMS]


@pytest.fixture()
def mock_populations():
    """Sample population data keyed by Wikipedia title."""
    return {k: v.copy() for k, v in MOCK_POPULATIONS.items()}
