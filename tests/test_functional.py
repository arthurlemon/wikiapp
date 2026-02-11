"""Functional tests that call real Wikipedia/Wikidata APIs.

These are slower and require network access, so they are marked with
``pytest.mark.functional`` and skipped by default.  Run them explicitly::

    pytest -m functional
"""

from __future__ import annotations

import pytest

from wikiapp.clients.wikidata import (
    _fetch_population_from_wikidata,
    _get_wikidata_item_id,
    get_city_population,
)

functional = pytest.mark.functional


# ---- _get_wikidata_item_id ----

@functional
def test_resolve_paris_item_id():
    item_id = _get_wikidata_item_id("Paris")
    assert item_id == "Q90"


@functional
def test_resolve_nonexistent_page():
    item_id = _get_wikidata_item_id("ThisPageDefinitelyDoesNotExist12345")
    assert item_id is None


# ---- _fetch_population_from_wikidata ----

@functional
def test_fetch_population_paris():
    """Paris (Q90) should have a population and a point-in-time date."""
    result = _fetch_population_from_wikidata("Q90")
    assert result is not None
    assert result["city"] == "Paris"
    assert result["wikidata_item_id"] == "Q90"
    assert result["population"] > 1_000_000
    assert result["population_as_of"] is not None


@functional
def test_fetch_population_london():
    """London (Q84) should return a large population."""
    result = _fetch_population_from_wikidata("Q84")
    assert result is not None
    assert result["population"] > 5_000_000


@functional
def test_fetch_population_invalid_item():
    """A non-existent Wikidata item should return None."""
    result = _fetch_population_from_wikidata("Q999999999")
    assert result is None


# ---- get_city_population (end-to-end) ----

@functional
def test_get_city_population_paris():
    """Full pipeline: Wikipedia title -> Wikidata item -> population."""
    result = get_city_population("Paris")
    assert result is not None
    assert result["city"] == "Paris"
    assert result["city_wikipedia_title"] == "Paris"
    assert result["population"] > 1_000_000
    assert "wikidata_item_id" in result


@functional
def test_get_city_population_new_york():
    result = get_city_population("New_York_City")
    assert result is not None
    assert result["population"] > 5_000_000


@functional
def test_get_city_population_unknown_city():
    result = get_city_population("ThisCityDoesNotExist12345")
    assert result is None
