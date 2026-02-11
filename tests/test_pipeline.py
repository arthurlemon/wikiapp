"""Unit tests that don't require a database connection."""

from __future__ import annotations

import pytest

from wikiapp.clients.wikipedia import (
    _bundled_snapshot,
    _extract_int,
    _extract_year,
    _normalize_city_title,
    fetch_museums,
    parse_museums_from_html,
)
from wikiapp.clients.wikidata import get_city_population, _CURATED_POPULATION
from wikiapp.config import settings


# ---- _extract_int ----

@pytest.mark.parametrize("raw, expected", [
    ("9,000,000 (2025) [ 1 ]", 9_000_000),
    ("6,956,800 (2024) [ 2 ]", 6_956_800),
    ("4,603,025 (2024) [10]", 4_603_025),
    ("5.7 million (FY 2024-25)", 5_700_000),
    ("3.1 million (2024)", 3_100_000),
    ("8,900,000", 8_900_000),
    ("2024", 2024),
    ("", None),
    ("no digits here", None),
])
def test_extract_int(raw, expected):
    assert _extract_int(raw) == expected


def test_extract_int_ignores_year_and_reference():
    """The old bug: digits from year and ref number were concatenated."""
    result = _extract_int("4,603,025 (2024) [10]")
    assert result == 4_603_025
    assert result < 10_000_000  # sanity: not 4603025202410


# ---- _extract_year ----

@pytest.mark.parametrize("raw, expected", [
    ("9,000,000 (2025) [ 1 ]", 2025),
    ("6,956,800 (2024) [ 2 ]", 2024),
    ("5.7 million (FY 2024-25)", 2024),
    ("3,100,000 (2023)", 2023),
    ("8,900,000", None),
    ("no year here", None),
    ("", None),
])
def test_extract_year(raw, expected):
    assert _extract_year(raw) == expected


# ---- _normalize_city_title ----

def _make_cell(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(f"<td>{html}</td>", "html.parser").find("td")


def test_normalize_city_title_plain():
    cell = _make_cell("<a href='/wiki/Paris'>Paris</a>")
    assert _normalize_city_title(cell) == "Paris"


def test_normalize_city_title_url_decoded():
    """URL-encoded hrefs should be decoded to avoid double-encoding."""
    cell = _make_cell("<a href='/wiki/Krak%C3%B3w'>Kraków</a>")
    assert _normalize_city_title(cell) == "Kraków"


def test_normalize_city_title_sao_paulo():
    cell = _make_cell("<a href='/wiki/S%C3%A3o_Paulo'>São Paulo</a>")
    assert _normalize_city_title(cell) == "São_Paulo"


def test_normalize_city_title_no_link():
    cell = _make_cell("Vatican City")
    assert _normalize_city_title(cell) == "Vatican_City"


# ---- parse_museums_from_html ----

def test_bundled_snapshot_has_enough_museums():
    museums = _bundled_snapshot()
    assert len(museums) >= 20
    for m in museums:
        assert m["annual_visitors"] >= settings.visitor_threshold


def test_fetch_museums_applies_threshold():
    """fetch_museums should filter below threshold (uses fallback here)."""
    museums = fetch_museums(threshold=5_000_000)
    assert all(m["annual_visitors"] >= 5_000_000 for m in museums)


# Old format: separate year column
SAMPLE_HTML_SEPARATE_YEAR = """
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


def test_parse_separate_year_column():
    rows = parse_museums_from_html(SAMPLE_HTML_SEPARATE_YEAR)
    assert len(rows) == 2
    assert rows[0]["museum_name"] == "Louvre"
    assert rows[0]["annual_visitors"] == 8_900_000
    assert rows[0]["attendance_year"] == 2024
    assert rows[0]["city_wikipedia_title"] == "Paris"


# Current Wikipedia format: year embedded in visitors cell
SAMPLE_HTML_INLINE_YEAR = """
<table class='wikitable'>
  <tr><th>Name</th><th>Visitors</th><th>City</th><th>Country</th></tr>
  <tr>
    <td>Louvre</td>
    <td>9,000,000 (2025) <sup>[1]</sup></td>
    <td><a href='/wiki/Paris'>Paris</a></td>
    <td>France</td>
  </tr>
  <tr>
    <td>Metropolitan Museum of Art</td>
    <td>5.7 million (FY 2024-25) <sup>[8]</sup></td>
    <td><a href='/wiki/New_York_City'>New York City</a></td>
    <td>United States</td>
  </tr>
  <tr>
    <td>National Museum in Kraków</td>
    <td>1,859,484 (2024) <sup>[46]</sup></td>
    <td><a href='/wiki/Krak%C3%B3w'>Kraków</a></td>
    <td>Poland</td>
  </tr>
</table>
"""


def test_parse_inline_year_format():
    rows = parse_museums_from_html(SAMPLE_HTML_INLINE_YEAR)
    assert len(rows) == 3

    assert rows[0]["annual_visitors"] == 9_000_000
    assert rows[0]["attendance_year"] == 2025

    # "X.Y million" format
    assert rows[1]["museum_name"] == "Metropolitan Museum of Art"
    assert rows[1]["annual_visitors"] == 5_700_000
    assert rows[1]["attendance_year"] == 2024

    # URL-decoded city title
    assert rows[2]["city_wikipedia_title"] == "Kraków"
    assert rows[2]["annual_visitors"] == 1_859_484


# ---- Wikidata / population client ----

def test_curated_population_fallback():
    """Curated lookup should return data for known cities."""
    result = get_city_population("Paris")
    assert result is not None
    assert result["population"] > 1_000_000  # Paris has >1M people


def test_unknown_city_returns_none():
    result = get_city_population("Nonexistent_Place_XYZ")
    assert result is None
