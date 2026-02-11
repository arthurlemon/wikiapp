"""Unit tests that don't require a database connection."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from wikiapp.clients.wikipedia import (
    _col_match,
    _extract_int,
    _extract_year,
    _title_from_href,
    parse_museums_from_html,
)
from wikiapp.clients.wikidata import _parse_population_statement
from wikiapp.schemas import PredictRequest


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


# ---- _title_from_href ----

def test_title_from_href_plain():
    assert _title_from_href("/wiki/Paris") == "Paris"


def test_title_from_href_url_decoded():
    """URL-encoded hrefs should be decoded to avoid double-encoding."""
    assert _title_from_href("/wiki/Krak%C3%B3w") == "Kraków"


def test_title_from_href_sao_paulo():
    assert _title_from_href("/wiki/S%C3%A3o_Paulo") == "São_Paulo"


def test_title_from_href_no_link():
    assert _title_from_href(None) is None


# ---- parse_museums_from_html ----

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


# ---- _col_match ----

def test_col_match_finds_first_match():
    assert _col_match(["name", "visitors", "city"], ["visitor"]) == "visitors"


def test_col_match_returns_none():
    assert _col_match(["name", "city"], ["visitor"]) is None


def test_col_match_prefers_first_header():
    """When multiple headers match, return the first one."""
    assert _col_match(["museum name", "name"], ["museum", "name"]) == "museum name"


# ---- parse_museums_from_html edge cases ----

def test_parse_no_matching_table():
    html = "<table><tr><th>Fruit</th><th>Color</th></tr></table>"
    with pytest.raises(ValueError, match="Could not find museum attendance table"):
        parse_museums_from_html(html)


def test_parse_city_without_href():
    """Cities without a wiki link should fall back to text-based title."""
    html = """
    <table>
      <tr><th>Name</th><th>Visitors</th><th>City</th><th>Country</th></tr>
      <tr>
        <td>Test Museum</td>
        <td>3,000,000 (2024)</td>
        <td>New York City</td>
        <td>United States</td>
      </tr>
    </table>
    """
    rows = parse_museums_from_html(html)
    assert rows[0]["city_wikipedia_title"] == "New_York_City"


def test_parse_without_country_column():
    """Table missing country column should still parse, with country=None."""
    html = """
    <table>
      <tr><th>Name</th><th>Visitors</th><th>City</th></tr>
      <tr>
        <td>Louvre</td>
        <td>8,900,000</td>
        <td><a href='/wiki/Paris'>Paris</a></td>
      </tr>
    </table>
    """
    rows = parse_museums_from_html(html)
    assert len(rows) == 1
    assert rows[0]["country"] is None
    assert rows[0]["museum_name"] == "Louvre"


# ---- _parse_population_statement ----

def test_parse_population_with_date():
    stmt = {
        "mainsnak": {"datavalue": {"value": {"amount": "+2161000"}}},
        "qualifiers": {"P585": [{"datavalue": {"value": {"time": "+2020-01-01T00:00:00Z"}}}]},
    }
    pop, as_of = _parse_population_statement(stmt)
    assert pop == 2_161_000
    assert as_of == date(2020, 1, 1)


def test_parse_population_without_date():
    stmt = {"mainsnak": {"datavalue": {"value": {"amount": "+905000"}}}}
    pop, as_of = _parse_population_statement(stmt)
    assert pop == 905_000
    assert as_of is None


def test_parse_population_empty_statement():
    pop, as_of = _parse_population_statement({})
    assert pop is None
    assert as_of is None


def test_parse_population_invalid_amount():
    stmt = {"mainsnak": {"datavalue": {"value": {"amount": "not-a-number"}}}}
    pop, as_of = _parse_population_statement(stmt)
    assert pop is None


# ---- PredictRequest validation ----

def test_predict_request_valid():
    req = PredictRequest(population=5_000_000)
    assert req.population == 5_000_000


def test_predict_request_rejects_zero():
    with pytest.raises(ValidationError):
        PredictRequest(population=0)


def test_predict_request_rejects_negative():
    with pytest.raises(ValidationError):
        PredictRequest(population=-1)
