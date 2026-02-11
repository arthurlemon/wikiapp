"""Unit tests that don't require a database connection."""

from __future__ import annotations

from wikiapp.clients.wikipedia import _bundled_snapshot, fetch_museums, parse_museums_from_html
from wikiapp.clients.wikidata import get_city_population, _CURATED_POPULATION
from wikiapp.config import settings


# ---- Wikipedia client ----

def test_bundled_snapshot_has_enough_museums():
    museums = _bundled_snapshot()
    assert len(museums) >= 20
    for m in museums:
        assert m["annual_visitors"] >= settings.visitor_threshold


def test_fetch_museums_applies_threshold():
    """fetch_museums should filter below threshold (uses fallback here)."""
    museums = fetch_museums(threshold=5_000_000)
    assert all(m["annual_visitors"] >= 5_000_000 for m in museums)


SAMPLE_HTML = """
<table class='wikitable'>
  <tr><th>Museum</th><th>City</th><th>Country</th><th>Visitors</th><th>Year</th></tr>
  <tr>
    <td>Louvre</td>
    <td><a href='/wiki/Paris'>Paris</a></td>
    <td>France</td>
    <td>8,900,000</td>
    <td>2024</td>
  </tr>
  <tr>
    <td>Old Museum</td>
    <td><a href='/wiki/Berlin'>Berlin</a></td>
    <td>Germany</td>
    <td>2,100,000</td>
    <td>2023</td>
  </tr>
</table>
"""


def test_parse_museums_from_html():
    rows = parse_museums_from_html(SAMPLE_HTML)
    assert len(rows) == 2
    assert rows[0]["museum_name"] == "Louvre"
    assert rows[0]["annual_visitors"] == 8_900_000
    assert rows[0]["city_wikipedia_title"] == "Paris"


# ---- Wikidata / population client ----

def test_curated_population_fallback():
    """Curated lookup should return data for known cities."""
    result = get_city_population("Paris")
    assert result is not None
    assert result["population"] == _CURATED_POPULATION["Paris"]


def test_unknown_city_returns_none():
    result = get_city_population("Nonexistent_Place_XYZ")
    assert result is None
