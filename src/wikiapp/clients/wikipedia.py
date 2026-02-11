"""Fetch museum data from the Wikipedia API.

Uses pandas.read_html for HTML table parsing.

The >2 M visitor threshold is applied at fetch time so downstream code
always works with the target population of museums.
"""

from __future__ import annotations

import logging
import re
from io import StringIO
from urllib.parse import unquote

import pandas as pd
import requests

from wikiapp.config import settings

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
MUSEUM_PAGE = "List_of_most-visited_museums"
SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_most_visited_museums"


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
    """Extract visitor count from a string, stopping at parentheses/brackets.

    Handles both numeric formats (``9,000,000``) and text formats
    (``5.7 million``).
    """
    # Take only the part before any '(' or '[' so year/refs aren't included
    clean = re.split(r"[(\[]", str(raw))[0]
    # Handle "X.Y million" format
    m = re.match(r"[\s]*([0-9]+(?:\.[0-9]+)?)\s*million", clean, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    digits = re.sub(r"[^\d]", "", clean)
    return int(digits) if digits else None


def _extract_year(raw: str) -> int | None:
    """Extract a 4-digit year from parenthesized text like '(2024)' or '(FY 2024-25)'."""
    match = re.search(r"\((?:FY\s+)?(\d{4})", str(raw))
    return int(match.group(1)) if match else None


def _title_from_href(href: str | None) -> str | None:
    """Extract Wikipedia page title from a /wiki/... href."""
    if href and href.startswith("/wiki/"):
        return unquote(href[len("/wiki/"):])
    return None


def _col_match(headers: list[str], candidates: list[str]) -> str | None:
    """Return the first header that contains any of the candidate substrings."""
    for h in headers:
        if any(c in h for c in candidates):
            return h
    return None


def parse_museums_from_html(html: str) -> list[dict]:
    """Parse the Wikipedia HTML into a list of museum dicts."""
    dfs = pd.read_html(StringIO(html), extract_links="all")

    # Find the table whose headers match the expected columns.
    df = None
    for candidate in dfs:
        headers = [str(c[0]).lower() for c in candidate.columns]
        has_museum = any("museum" in h or h == "name" for h in headers)
        has_city = any("city" in h or "location" in h for h in headers)
        has_visitors = any("visitor" in h or "attendance" in h for h in headers)
        if has_museum and has_city and has_visitors:
            df = candidate
            break

    if df is None:
        raise ValueError("Could not find museum attendance table in Wikipedia HTML")

    # Resolve column names (each header is a (text, href) tuple).
    headers = [str(c[0]).lower() for c in df.columns]
    mc = _col_match(headers, ["museum", "name"])
    cc = _col_match(headers, ["city", "location"])
    co = _col_match(headers, ["country"])
    vc = _col_match(headers, ["visitor", "attendance"])
    yc = _col_match(headers, ["year"])

    if mc is None or cc is None or vc is None:
        raise ValueError(f"Missing required columns in headers: {headers}")

    # Map lowercase names back to original DataFrame column tuples.
    col_map = {str(c[0]).lower(): c for c in df.columns}

    rows: list[dict] = []
    for _, row in df.iterrows():
        name_text, _ = row[col_map[mc]]
        if not name_text:
            continue

        visitor_text, _ = row[col_map[vc]]
        city_text, city_href = row[col_map[cc]]

        country = None
        if co is not None and col_map.get(co) is not None:
            country_text, _ = row[col_map[co]]
            country = country_text

        # Year: from a dedicated column if present, otherwise from visitor text.
        if yc is not None and col_map.get(yc) is not None:
            year_text, _ = row[col_map[yc]]
            attendance_year = _extract_int(str(year_text))
        else:
            attendance_year = _extract_year(str(visitor_text))

        city_title = _title_from_href(city_href)
        if city_title is None:
            # No link — derive from the text.
            clean = re.sub(r"\[.*?\]", "", str(city_text)).split(",")[0].strip()
            city_title = clean.replace(" ", "_") if clean else None

        rows.append({
            "museum_name": str(name_text),
            "city": str(city_text),
            "country": country,
            "annual_visitors": _extract_int(str(visitor_text)),
            "attendance_year": attendance_year,
            "city_wikipedia_title": city_title,
            "source_url": SOURCE_URL,
        })
    return rows


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def fetch_museums(threshold: int | None = None) -> list[dict]:
    """Fetch museums from Wikipedia API, applying a visitor threshold."""
    threshold = threshold or settings.visitor_threshold

    html = _fetch_html()
    museums = parse_museums_from_html(html)
    logger.info("Fetched %d museums from Wikipedia API", len(museums))

    filtered = [
        m for m in museums
        if m.get("annual_visitors") is not None and m["annual_visitors"] >= threshold
    ]
    logger.info("Returning %d museums with >= %d visitors", len(filtered), threshold)
    return filtered
