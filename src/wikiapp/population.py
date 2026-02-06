"""Fetch city population data.

Strategy:
- Use Wikipedia API to query city pages and extract population from infoboxes.
- Wikipedia exposes structured "wbgetentities" via Wikidata for population (P1082),
  but the simpler approach is to query the TextExtracts API for the city page intro
  and extract the population figure from the infobox HTML.
- A bundled lookup table is used as the primary source for reliability and speed.
  The Wikipedia-based enrichment is attempted second and can be enabled via the CLI.

Trade-off rationale:
- City populations are slow-changing. A curated lookup is more reliable than
  scraping variable-format Wikipedia infoboxes for an MVP.
- For production, Wikidata SPARQL or a dedicated demographics API (e.g., World Bank)
  would be a better source. See README for next steps.
"""

from __future__ import annotations

import logging
import re

import requests

logger = logging.getLogger(__name__)

# Curated population data (metro or city proper, most recent available).
# Source: Wikipedia / UN World Urbanization Prospects.
_POPULATION_LOOKUP: dict[str, int] = {
    "Paris": 2_161_000,
    "Beijing": 21_540_000,
    "Vatican City": 825,
    "London": 8_982_000,
    "New York City": 8_336_000,
    "Washington, D.C.": 689_000,
    "Saint Petersburg": 5_384_000,
    "Shanghai": 24_870_000,
    "Taipei": 2_646_000,
    "Madrid": 3_223_000,
    "Seoul": 9_776_000,
    "Hangzhou": 12_200_000,
    "Amsterdam": 905_000,
    "Nanjing": 9_430_000,
    "Melbourne": 5_078_000,
    "Athens": 3_154_000,
    "Florence": 382_000,
    "Tokyo": 13_960_000,
    "Moscow": 12_630_000,
    "Mexico City": 9_210_000,
    "Munich": 1_472_000,
    "Singapore": 5_686_000,
    "San Francisco": 874_000,
    "Los Angeles": 3_979_000,
    "Chicago": 2_696_000,
    "Toronto": 2_794_000,
    "Berlin": 3_645_000,
    "Vienna": 1_982_000,
    "Rome": 2_873_000,
    "Bangkok": 10_540_000,
    "Istanbul": 15_460_000,
    "Cairo": 10_100_000,
    "Dubai": 3_490_000,
    "Kuala Lumpur": 1_982_000,
    "Jakarta": 10_560_000,
    "Bogotá": 7_181_000,
    "Buenos Aires": 3_121_000,
    "Lima": 9_752_000,
    "São Paulo": 12_330_000,
    "Doha": 2_382_000,
    "Abu Dhabi": 1_540_000,
}


def get_city_population(city: str) -> int | None:
    """Return population for a city. Tries local lookup, then Wikipedia API."""
    # Normalize common variants
    normalized = city.strip()
    pop = _POPULATION_LOOKUP.get(normalized)
    if pop is not None:
        return pop

    # Try Wikipedia API as fallback
    pop = _fetch_population_from_wikipedia(normalized)
    if pop is not None:
        _POPULATION_LOOKUP[normalized] = pop  # memoize
    return pop


def _fetch_population_from_wikipedia(city: str, timeout: int = 15) -> int | None:
    """Attempt to extract population from the Wikipedia city page infobox HTML."""
    params = {
        "action": "parse",
        "page": city,
        "prop": "text",
        "format": "json",
        "formatversion": "2",
        "section": "0",  # intro only (contains infobox)
    }
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php", params=params, timeout=timeout
        )
        resp.raise_for_status()
        html = resp.json()["parse"]["text"]
    except (requests.RequestException, KeyError):
        logger.debug("Could not fetch Wikipedia page for city: %s", city)
        return None

    # Look for population figures in infobox — typically a <td> after a "Population" <th>
    # This is intentionally simple; a production system would use Wikidata SPARQL.
    m = re.search(r"(?:population|Population)[^<]*</th>\s*<td[^>]*>\s*([\d,]+)", html)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def enrich_museums_with_population(
    museums: list[dict],
) -> list[dict]:
    """Add 'city_population' key to each museum dict."""
    for m in museums:
        m["city_population"] = get_city_population(m["city"])
    return museums
