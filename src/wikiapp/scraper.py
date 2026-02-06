"""Fetch museum data from Wikipedia API.

Strategy:
- Use the MediaWiki API to parse the "List of most-visited museums" page.
- Extract the HTML table and parse it with stdlib html.parser to avoid
  a heavy dependency on beautifulsoup4.
- Fall back to a bundled snapshot when the API is unreachable (CI, airgapped envs).

Known limitations:
- Wikipedia tables change format over time; the parser targets the current
  column layout and will need maintenance if columns are added/reordered.
- The API returns rendered HTML, which is more stable than wikitext but
  still subject to template changes.
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"
PAGE_TITLE = "List of most-visited museums"
VISITOR_THRESHOLD = 2_000_000
CACHE_PATH = Path(__file__).parent / "data" / "museums_cache.json"


# ---------------------------------------------------------------------------
# Lightweight HTML table parser (avoids BeautifulSoup dependency)
# ---------------------------------------------------------------------------

class _TableParser(HTMLParser):
    """Extract rows from the first <table> with class 'wikitable'."""

    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.in_header = False
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._table_depth = 0
        self._link_text: list[str] = []
        self._in_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if tag == "table" and "wikitable" in (attr_dict.get("class") or ""):
            self.in_table = True
            self._table_depth += 1
        elif self.in_table:
            if tag == "tr":
                self.in_row = True
                self._current_row = []
            elif tag == "th":
                self.in_header = True
                self.in_cell = True
                self._current_cell = []
            elif tag == "td":
                self.in_cell = True
                self._current_cell = []
            elif tag == "a" and self.in_cell:
                self._in_link = True
                self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            self._in_link = False
            # Prefer link text over surrounding text for museum/city names
            if self._link_text:
                self._current_cell.append("".join(self._link_text))
                self._link_text = []
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            self.in_header = False
            self._current_row.append("".join(self._current_cell).strip())
            self._current_cell = []
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self._current_row:
                self.rows.append(self._current_row)
        elif tag == "table" and self.in_table:
            self._table_depth -= 1
            if self._table_depth == 0:
                self.in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._link_text.append(data)
        elif self.in_cell:
            self._current_cell.append(data)


def _parse_visitor_count(raw: str) -> int | None:
    """Extract numeric visitor count from a string like '10,000,000' or '9.2 million'."""
    raw = raw.replace(",", "").replace("\xa0", "").strip()
    # Try plain integer
    m = re.search(r"([\d]+(?:\.\d+)?)", raw)
    if not m:
        return None
    val = float(m.group(1))
    if "million" in raw.lower():
        val *= 1_000_000
    return int(val)


def _parse_table(html: str) -> list[dict[str, Any]]:
    """Parse the HTML table into a list of museum dicts."""
    parser = _TableParser()
    parser.feed(html)

    if not parser.rows:
        return []

    # First row is headers
    headers = [h.lower().strip() for h in parser.rows[0]]
    museums: list[dict[str, Any]] = []

    for row in parser.rows[1:]:
        if len(row) < len(headers):
            continue
        record = dict(zip(headers, row))

        # Normalize column names (Wikipedia may use varying names)
        name = record.get("name") or record.get("museum") or ""
        city = record.get("city") or record.get("location") or ""
        country = record.get("country") or record.get("nation") or ""
        visitors_raw = record.get("visitors") or record.get("visitor count") or ""
        # Also try columns containing "visitor" in the name
        if not visitors_raw:
            for k, v in record.items():
                if "visitor" in k:
                    visitors_raw = v
                    break

        visitors = _parse_visitor_count(visitors_raw)
        if not name or visitors is None:
            continue

        museums.append({
            "name": name.strip(),
            "city": city.strip(),
            "country": country.strip(),
            "visitors": visitors,
        })

    return museums


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_museums_from_wikipedia(timeout: int = 30) -> list[dict[str, Any]]:
    """Fetch and parse the museum list from Wikipedia API.

    Returns a list of dicts with keys: name, city, country, visitors.
    Only museums with >= VISITOR_THRESHOLD visitors are returned.
    """
    params = {
        "action": "parse",
        "page": PAGE_TITLE,
        "prop": "text",
        "format": "json",
        "formatversion": "2",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        html = resp.json()["parse"]["text"]
    except (requests.RequestException, KeyError) as exc:
        logger.warning("Wikipedia API unavailable (%s), using cached data", exc)
        return _load_cache()

    museums = _parse_table(html)
    filtered = [m for m in museums if m["visitors"] >= VISITOR_THRESHOLD]
    logger.info("Fetched %d museums (>=%d visitors) from Wikipedia", len(filtered), VISITOR_THRESHOLD)

    # Persist cache for offline use
    _save_cache(filtered)
    return filtered


def _load_cache() -> list[dict[str, Any]]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    # Ultimate fallback: bundled snapshot
    return _bundled_snapshot()


def _save_cache(museums: list[dict[str, Any]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(museums, indent=2))


def _bundled_snapshot() -> list[dict[str, Any]]:
    """Hardcoded snapshot from Wikipedia (2023 data) for environments without
    network access. This ensures the pipeline always works end-to-end."""
    return [
        {"name": "Louvre", "city": "Paris", "country": "France", "visitors": 8_900_000},
        {"name": "National Museum of China", "city": "Beijing", "country": "China", "visitors": 7_290_000},
        {"name": "Vatican Museums", "city": "Vatican City", "country": "Vatican City", "visitors": 6_770_000},
        {"name": "Natural History Museum", "city": "London", "country": "United Kingdom", "visitors": 5_810_000},
        {"name": "British Museum", "city": "London", "country": "United Kingdom", "visitors": 5_820_000},
        {"name": "Tate Modern", "city": "London", "country": "United Kingdom", "visitors": 5_570_000},
        {"name": "National Gallery", "city": "London", "country": "United Kingdom", "visitors": 5_250_000},
        {"name": "The Metropolitan Museum of Art", "city": "New York City", "country": "United States", "visitors": 5_360_000},
        {"name": "National Gallery of Art", "city": "Washington, D.C.", "country": "United States", "visitors": 4_210_000},
        {"name": "State Hermitage Museum", "city": "Saint Petersburg", "country": "Russia", "visitors": 3_570_000},
        {"name": "Shanghai Science and Technology Museum", "city": "Shanghai", "country": "China", "visitors": 4_820_000},
        {"name": "National Museum of Natural History", "city": "Washington, D.C.", "country": "United States", "visitors": 4_200_000},
        {"name": "National Air and Space Museum", "city": "Washington, D.C.", "country": "United States", "visitors": 3_200_000},
        {"name": "Victoria and Albert Museum", "city": "London", "country": "United Kingdom", "visitors": 4_000_000},
        {"name": "Science Museum", "city": "London", "country": "United Kingdom", "visitors": 3_300_000},
        {"name": "Musée d'Orsay", "city": "Paris", "country": "France", "visitors": 3_270_000},
        {"name": "Centre Pompidou", "city": "Paris", "country": "France", "visitors": 3_010_000},
        {"name": "National Palace Museum", "city": "Taipei", "country": "Taiwan", "visitors": 3_830_000},
        {"name": "Reina Sofía", "city": "Madrid", "country": "Spain", "visitors": 3_900_000},
        {"name": "Museo del Prado", "city": "Madrid", "country": "Spain", "visitors": 3_200_000},
        {"name": "National Museum of Korea", "city": "Seoul", "country": "South Korea", "visitors": 3_350_000},
        {"name": "Zhejiang Museum", "city": "Hangzhou", "country": "China", "visitors": 3_600_000},
        {"name": "China Science Technology Museum", "city": "Beijing", "country": "China", "visitors": 3_880_000},
        {"name": "National Museum of American History", "city": "Washington, D.C.", "country": "United States", "visitors": 2_800_000},
        {"name": "Rijksmuseum", "city": "Amsterdam", "country": "Netherlands", "visitors": 2_700_000},
        {"name": "Van Gogh Museum", "city": "Amsterdam", "country": "Netherlands", "visitors": 2_160_000},
        {"name": "Nanjing Museum", "city": "Nanjing", "country": "China", "visitors": 4_170_000},
        {"name": "National Gallery of Victoria", "city": "Melbourne", "country": "Australia", "visitors": 3_200_000},
        {"name": "Somerset House", "city": "London", "country": "United Kingdom", "visitors": 3_200_000},
        {"name": "Acropolis Museum", "city": "Athens", "country": "Greece", "visitors": 2_100_000},
        {"name": "Uffizi Galleries", "city": "Florence", "country": "Italy", "visitors": 2_100_000},
        {"name": "Tokyo National Museum", "city": "Tokyo", "country": "Japan", "visitors": 2_300_000},
        {"name": "American Museum of Natural History", "city": "New York City", "country": "United States", "visitors": 3_100_000},
    ]
