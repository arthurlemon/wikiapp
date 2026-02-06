"""SQLite database layer.

Design rationale:
- SQLite is chosen for the MVP: zero-config, single-file, ships with Python.
- The schema is intentionally normalized (museums + cities) to allow independent
  updates and to model the one-to-many relationship (multiple museums per city).
- For production scale, swap the connection string to PostgreSQL via SQLAlchemy
  or similar — the interface (init_db / insert_* / query) stays the same.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/museums.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL,
    population  INTEGER,
    UNIQUE(name, country)
);

CREATE TABLE IF NOT EXISTS museums (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    city_id         INTEGER NOT NULL REFERENCES cities(id),
    visitors        INTEGER NOT NULL,
    UNIQUE(name)
);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_city(conn: sqlite3.Connection, name: str, country: str, population: int | None) -> int:
    """Insert or update a city, return its id."""
    conn.execute(
        """INSERT INTO cities (name, country, population) VALUES (?, ?, ?)
           ON CONFLICT(name, country) DO UPDATE SET population = excluded.population""",
        (name, country, population),
    )
    conn.commit()
    cur = conn.execute("SELECT id FROM cities WHERE name = ? AND country = ?", (name, country))
    return cur.fetchone()[0]


def upsert_museum(conn: sqlite3.Connection, name: str, city_id: int, visitors: int) -> int:
    conn.execute(
        """INSERT INTO museums (name, city_id, visitors) VALUES (?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET city_id = excluded.city_id, visitors = excluded.visitors""",
        (name, city_id, visitors),
    )
    conn.commit()
    cur = conn.execute("SELECT id FROM museums WHERE name = ?", (name,))
    return cur.fetchone()[0]


def load_museums(museums_data: list[dict[str, Any]], conn: sqlite3.Connection) -> None:
    """Bulk-load museum data into the DB."""
    for m in museums_data:
        city_id = upsert_city(conn, m["city"], m["country"], m.get("city_population"))
        upsert_museum(conn, m["name"], city_id, m["visitors"])
    logger.info("Loaded %d museums into database", len(museums_data))


def query_dataset(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return a joined DataFrame of museums + city population for analysis."""
    query = """
        SELECT
            m.name       AS museum,
            c.name       AS city,
            c.country    AS country,
            m.visitors   AS visitors,
            c.population AS city_population
        FROM museums m
        JOIN cities c ON m.city_id = c.id
        WHERE c.population IS NOT NULL
        ORDER BY m.visitors DESC
    """
    return pd.read_sql_query(query, conn)
