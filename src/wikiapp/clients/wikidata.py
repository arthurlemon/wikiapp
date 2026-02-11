"""Fetch city population from Wikidata (P1082 property)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests

from wikiapp.config import settings

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"


# ------------------------------------------------------------------
# Wikidata API helpers
# ------------------------------------------------------------------

def _headers() -> dict[str, str]:
    h = {"User-Agent": settings.wikipedia_user_agent, "Accept": "application/json"}
    if settings.wikidata_token:
        h["Authorization"] = f"Bearer {settings.wikidata_token}"
    return h


def _get_wikidata_item_id(wikipedia_title: str) -> str | None:
    """Resolve a Wikipedia page title to a Wikidata item ID (e.g. Q90 for Paris)."""
    params = {
        "action": "query",
        "titles": wikipedia_title,
        "prop": "pageprops",
        "format": "json",
    }
    resp = requests.get(WIKIPEDIA_API, params=params, headers=_headers(), timeout=15)
    resp.raise_for_status()
    for page in resp.json().get("query", {}).get("pages", {}).values():
        item_id = page.get("pageprops", {}).get("wikibase_item")
        if item_id:
            return item_id
    return None


def _parse_population_statement(stmt: dict[str, Any]) -> tuple[int | None, date | None]:
    """Extract population value and point-in-time qualifier from a Wikidata claim."""
    amount = stmt.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("amount")
    population = None
    if isinstance(amount, str):
        try:
            population = int(amount.replace("+", ""))
        except ValueError:
            pass
    elif isinstance(amount, (int, float)):
        population = int(amount)

    as_of = None
    for pit in stmt.get("qualifiers", {}).get("P585", []):
        raw = pit.get("datavalue", {}).get("value", {}).get("time")
        if isinstance(raw, str) and raw.startswith("+"):
            try:
                as_of = date.fromisoformat(raw[1:11])
            except ValueError:
                pass
    return population, as_of


def _fetch_population_from_wikidata(item_id: str) -> dict[str, Any] | None:
    """Fetch the most recent population figure from Wikidata for a given item."""
    params = {
        "action": "wbgetentities",
        "ids": item_id,
        "props": "labels|claims",
        "languages": "en",
        "format": "json",
    }
    resp = requests.get(WIKIDATA_API, params=params, headers=_headers(), timeout=15)
    resp.raise_for_status()
    entity = resp.json().get("entities", {}).get(item_id)
    if not entity:
        return None

    labels = entity.get("labels", {})
    city_name = labels.get("en", {}).get("value") or item_id

    claims = entity.get("claims", {}).get("P1082", [])
    parsed = [_parse_population_statement(c) for c in claims]
    parsed = [(p, d) for p, d in parsed if p is not None]
    if not parsed:
        return None

    # Prefer most recent dated value
    with_dates = [(p, d) for p, d in parsed if d is not None]
    if with_dates:
        with_dates.sort(key=lambda x: x[1])
        population, as_of = with_dates[-1]
    else:
        parsed.sort(key=lambda x: x[0])
        population, as_of = parsed[-1]

    return {
        "city": city_name,
        "wikidata_item_id": item_id,
        "population": population,
        "population_as_of": as_of,
    }


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def get_city_population(city_wikipedia_title: str) -> dict[str, Any] | None:
    """Return population data for a city from Wikidata."""
    item_id = _get_wikidata_item_id(city_wikipedia_title)
    if not item_id:
        return None
    result = _fetch_population_from_wikidata(item_id)
    if result:
        logger.debug("Wikidata population for %s: %s", city_wikipedia_title, result["population"])
        return {**result, "city_wikipedia_title": city_wikipedia_title}
    return None
