"""Fetch museum data from the Wikipedia API.

Uses BeautifulSoup for robust HTML table parsing.  Falls back to a bundled
JSON snapshot when the API is unreachable (CI, air-gapped environments).

The >2 M visitor threshold is applied at fetch time so downstream code
always works with the target population of museums.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from wikiapp.config import settings

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
MUSEUM_PAGE = "List_of_most-visited_museums"
SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_most_visited_museums"
CACHE_PATH = Path(__file__).parent.parent / "data" / "museums_cache.json"


# ------------------------------------------------------------------
# HTML fetch
# ------------------------------------------------------------------

def _fetch_html() -> str:
    headers = {"User-Agent": settings.wikipedia_user_agent}
    params = {
        "action": "parse",
        "page": MUSEUM_PAGE,
        "prop": "text",
        "format": "json",
        "formatversion": 2,
    }
    resp = requests.get(WIKIPEDIA_API, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["parse"]["text"]


# ------------------------------------------------------------------
# Parsing
# ------------------------------------------------------------------

def _extract_int(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def _normalize_city_title(cell) -> str | None:
    """Extract Wikipedia page title from a <td> cell, preferring <a href>."""
    anchor = cell.find("a", href=re.compile(r"^/wiki/"))
    if anchor and anchor.get("href", "").startswith("/wiki/"):
        return anchor["href"].replace("/wiki/", "", 1)
    text = re.sub(r"\[.*?\]", "", cell.get_text(" ", strip=True)).split(",")[0].strip()
    return text.replace(" ", "_") if text else None


def _find_target_table(soup: BeautifulSoup):
    """Locate the first wikitable whose headers match the expected columns."""
    for table in soup.find_all("table"):
        headers = [
            re.sub(r"\s+", " ", th.get_text(" ", strip=True).lower())
            for th in table.find_all("th")
        ]
        has_museum = any("museum" in h or h == "name" for h in headers)
        has_city = any("city" in h or "location" in h for h in headers)
        has_visitors = any("visitor" in h or "attendance" in h for h in headers)
        if has_museum and has_city and has_visitors:
            return table, headers
    return None, []


def _col_index(headers: list[str], candidates: list[str]) -> int | None:
    for i, h in enumerate(headers):
        if any(c in h for c in candidates):
            return i
    return None


def parse_museums_from_html(html: str) -> list[dict]:
    """Parse the Wikipedia HTML into a list of museum dicts."""
    soup = BeautifulSoup(html, "html.parser")
    table, headers = _find_target_table(soup)
    if table is None:
        raise ValueError("Could not find museum attendance table in Wikipedia HTML")

    mi = _col_index(headers, ["museum", "name"])
    ci = _col_index(headers, ["city", "location"])
    co = _col_index(headers, ["country"])
    vi = _col_index(headers, ["visitor", "attendance"])
    yi = _col_index(headers, ["year"])

    if mi is None or ci is None or vi is None:
        raise ValueError(f"Missing required columns in headers: {headers}")

    rows: list[dict] = []
    for tr in table.find_all("tr")[1:]:
        cols = tr.find_all("td")
        required_max = max(mi, ci, vi)
        if len(cols) <= required_max:
            continue

        name = cols[mi].get_text(" ", strip=True)
        if not name:
            continue

        rows.append({
            "museum_name": name,
            "city": cols[ci].get_text(" ", strip=True),
            "country": cols[co].get_text(" ", strip=True) if co is not None and co < len(cols) else None,
            "annual_visitors": _extract_int(cols[vi].get_text(" ", strip=True)),
            "attendance_year": _extract_int(cols[yi].get_text(" ", strip=True)) if yi is not None and yi < len(cols) else None,
            "city_wikipedia_title": _normalize_city_title(cols[ci]),
            "source_url": SOURCE_URL,
        })
    return rows


# ------------------------------------------------------------------
# Cache / fallback
# ------------------------------------------------------------------

def _save_cache(museums: list[dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(museums, indent=2, default=str))


def _load_cache() -> list[dict]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return _bundled_snapshot()


def _bundled_snapshot() -> list[dict]:
    """Hardcoded snapshot for environments without network access."""
    return [
        {"museum_name": "Louvre", "city": "Paris", "country": "France", "annual_visitors": 8_900_000, "attendance_year": 2024, "city_wikipedia_title": "Paris", "source_url": SOURCE_URL},
        {"museum_name": "National Museum of China", "city": "Beijing", "country": "China", "annual_visitors": 7_290_000, "attendance_year": 2024, "city_wikipedia_title": "Beijing", "source_url": SOURCE_URL},
        {"museum_name": "Vatican Museums", "city": "Vatican City", "country": "Vatican City", "annual_visitors": 6_770_000, "attendance_year": 2024, "city_wikipedia_title": "Vatican_City", "source_url": SOURCE_URL},
        {"museum_name": "Natural History Museum", "city": "London", "country": "United Kingdom", "annual_visitors": 5_810_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
        {"museum_name": "British Museum", "city": "London", "country": "United Kingdom", "annual_visitors": 5_820_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
        {"museum_name": "Tate Modern", "city": "London", "country": "United Kingdom", "annual_visitors": 5_570_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
        {"museum_name": "The Metropolitan Museum of Art", "city": "New York City", "country": "United States", "annual_visitors": 5_360_000, "attendance_year": 2024, "city_wikipedia_title": "New_York_City", "source_url": SOURCE_URL},
        {"museum_name": "National Gallery", "city": "London", "country": "United Kingdom", "annual_visitors": 5_250_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
        {"museum_name": "Shanghai Science and Technology Museum", "city": "Shanghai", "country": "China", "annual_visitors": 4_820_000, "attendance_year": 2024, "city_wikipedia_title": "Shanghai", "source_url": SOURCE_URL},
        {"museum_name": "National Gallery of Art", "city": "Washington, D.C.", "country": "United States", "annual_visitors": 4_210_000, "attendance_year": 2024, "city_wikipedia_title": "Washington,_D.C.", "source_url": SOURCE_URL},
        {"museum_name": "National Museum of Natural History", "city": "Washington, D.C.", "country": "United States", "annual_visitors": 4_200_000, "attendance_year": 2024, "city_wikipedia_title": "Washington,_D.C.", "source_url": SOURCE_URL},
        {"museum_name": "Nanjing Museum", "city": "Nanjing", "country": "China", "annual_visitors": 4_170_000, "attendance_year": 2024, "city_wikipedia_title": "Nanjing", "source_url": SOURCE_URL},
        {"museum_name": "Victoria and Albert Museum", "city": "London", "country": "United Kingdom", "annual_visitors": 4_000_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
        {"museum_name": "Reina Sofía", "city": "Madrid", "country": "Spain", "annual_visitors": 3_900_000, "attendance_year": 2024, "city_wikipedia_title": "Madrid", "source_url": SOURCE_URL},
        {"museum_name": "China Science Technology Museum", "city": "Beijing", "country": "China", "annual_visitors": 3_880_000, "attendance_year": 2024, "city_wikipedia_title": "Beijing", "source_url": SOURCE_URL},
        {"museum_name": "National Palace Museum", "city": "Taipei", "country": "Taiwan", "annual_visitors": 3_830_000, "attendance_year": 2024, "city_wikipedia_title": "Taipei", "source_url": SOURCE_URL},
        {"museum_name": "Zhejiang Museum", "city": "Hangzhou", "country": "China", "annual_visitors": 3_600_000, "attendance_year": 2024, "city_wikipedia_title": "Hangzhou", "source_url": SOURCE_URL},
        {"museum_name": "State Hermitage Museum", "city": "Saint Petersburg", "country": "Russia", "annual_visitors": 3_570_000, "attendance_year": 2024, "city_wikipedia_title": "Saint_Petersburg", "source_url": SOURCE_URL},
        {"museum_name": "National Museum of Korea", "city": "Seoul", "country": "South Korea", "annual_visitors": 3_350_000, "attendance_year": 2024, "city_wikipedia_title": "Seoul", "source_url": SOURCE_URL},
        {"museum_name": "Science Museum", "city": "London", "country": "United Kingdom", "annual_visitors": 3_300_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
        {"museum_name": "Musée d'Orsay", "city": "Paris", "country": "France", "annual_visitors": 3_270_000, "attendance_year": 2024, "city_wikipedia_title": "Paris", "source_url": SOURCE_URL},
        {"museum_name": "National Gallery of Victoria", "city": "Melbourne", "country": "Australia", "annual_visitors": 3_200_000, "attendance_year": 2024, "city_wikipedia_title": "Melbourne", "source_url": SOURCE_URL},
        {"museum_name": "Museo del Prado", "city": "Madrid", "country": "Spain", "annual_visitors": 3_200_000, "attendance_year": 2024, "city_wikipedia_title": "Madrid", "source_url": SOURCE_URL},
        {"museum_name": "Somerset House", "city": "London", "country": "United Kingdom", "annual_visitors": 3_200_000, "attendance_year": 2024, "city_wikipedia_title": "London", "source_url": SOURCE_URL},
        {"museum_name": "National Air and Space Museum", "city": "Washington, D.C.", "country": "United States", "annual_visitors": 3_200_000, "attendance_year": 2024, "city_wikipedia_title": "Washington,_D.C.", "source_url": SOURCE_URL},
        {"museum_name": "American Museum of Natural History", "city": "New York City", "country": "United States", "annual_visitors": 3_100_000, "attendance_year": 2024, "city_wikipedia_title": "New_York_City", "source_url": SOURCE_URL},
        {"museum_name": "Centre Pompidou", "city": "Paris", "country": "France", "annual_visitors": 3_010_000, "attendance_year": 2024, "city_wikipedia_title": "Paris", "source_url": SOURCE_URL},
        {"museum_name": "National Museum of American History", "city": "Washington, D.C.", "country": "United States", "annual_visitors": 2_800_000, "attendance_year": 2024, "city_wikipedia_title": "Washington,_D.C.", "source_url": SOURCE_URL},
        {"museum_name": "Rijksmuseum", "city": "Amsterdam", "country": "Netherlands", "annual_visitors": 2_700_000, "attendance_year": 2024, "city_wikipedia_title": "Amsterdam", "source_url": SOURCE_URL},
        {"museum_name": "Tokyo National Museum", "city": "Tokyo", "country": "Japan", "annual_visitors": 2_300_000, "attendance_year": 2024, "city_wikipedia_title": "Tokyo", "source_url": SOURCE_URL},
        {"museum_name": "Van Gogh Museum", "city": "Amsterdam", "country": "Netherlands", "annual_visitors": 2_160_000, "attendance_year": 2024, "city_wikipedia_title": "Amsterdam", "source_url": SOURCE_URL},
        {"museum_name": "Acropolis Museum", "city": "Athens", "country": "Greece", "annual_visitors": 2_100_000, "attendance_year": 2024, "city_wikipedia_title": "Athens", "source_url": SOURCE_URL},
        {"museum_name": "Uffizi Galleries", "city": "Florence", "country": "Italy", "annual_visitors": 2_100_000, "attendance_year": 2024, "city_wikipedia_title": "Florence", "source_url": SOURCE_URL},
    ]


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def fetch_museums(threshold: int | None = None) -> list[dict]:
    """Fetch museums from Wikipedia API, applying a visitor threshold.

    Falls back to cached/bundled data when the API is unreachable.
    """
    threshold = threshold or settings.visitor_threshold

    try:
        html = _fetch_html()
        museums = parse_museums_from_html(html)
        logger.info("Fetched %d museums from Wikipedia API", len(museums))
        _save_cache(museums)
    except Exception as exc:
        logger.warning("Wikipedia API unavailable (%s), using cached data", exc)
        museums = _load_cache()

    filtered = [
        m for m in museums
        if m.get("annual_visitors") is not None and m["annual_visitors"] >= threshold
    ]
    logger.info("Returning %d museums with >= %d visitors", len(filtered), threshold)
    return filtered
