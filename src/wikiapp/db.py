"""Database layer using SQLAlchemy Core.

Supports both PostgreSQL (production / Docker) and SQLite (local dev / tests).
The backend is selected via DATABASE_URL environment variable:
  - postgresql://user:pass@host/db  → PostgreSQL
  - sqlite:///path/to/file.db       → SQLite (default)

Design rationale:
- SQLAlchemy Core (not ORM) keeps the abstraction thin — we define tables
  declaratively but write queries as plain SQL expressions. This avoids
  the cognitive overhead of an ORM while handling dialect differences
  (SERIAL vs AUTOINCREMENT, ON CONFLICT syntax) transparently.
- The same Python code works against both backends, so tests run on SQLite
  in-memory while Docker Compose uses PostgreSQL.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:///data/museums.db"

metadata = MetaData()

cities_table = Table(
    "cities",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("country", String, nullable=False),
    Column("population", Integer),
    UniqueConstraint("name", "country"),
)

museums_table = Table(
    "museums",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False, unique=True),
    Column("city_id", Integer, ForeignKey("cities.id"), nullable=False),
    Column("visitors", Integer, nullable=False),
)


def get_engine(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine from a URL or the DATABASE_URL env var."""
    url = url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_engine(url, echo=False)


def init_db(engine: Engine) -> None:
    """Create tables if they don't exist."""
    metadata.create_all(engine)
    logger.info("Database initialized (%s)", engine.url.drivername)


def _upsert_city(conn, engine: Engine, name: str, country: str, population: int | None) -> int:
    """Insert or update a city, return its id."""
    if engine.dialect.name == "postgresql":
        stmt = (
            pg_insert(cities_table)
            .values(name=name, country=country, population=population)
            .on_conflict_do_update(
                constraint="cities_name_country_key",
                set_={"population": population},
            )
            .returning(cities_table.c.id)
        )
        result = conn.execute(stmt)
        return result.scalar_one()
    else:
        # SQLite
        stmt = (
            sqlite_insert(cities_table)
            .values(name=name, country=country, population=population)
            .on_conflict_do_update(
                index_elements=["name", "country"],
                set_={"population": population},
            )
        )
        conn.execute(stmt)
        row = conn.execute(
            select(cities_table.c.id).where(
                cities_table.c.name == name, cities_table.c.country == country
            )
        ).fetchone()
        return row[0]


def _upsert_museum(conn, engine: Engine, name: str, city_id: int, visitors: int) -> int:
    if engine.dialect.name == "postgresql":
        stmt = (
            pg_insert(museums_table)
            .values(name=name, city_id=city_id, visitors=visitors)
            .on_conflict_do_update(
                constraint="museums_name_key",
                set_={"city_id": city_id, "visitors": visitors},
            )
            .returning(museums_table.c.id)
        )
        result = conn.execute(stmt)
        return result.scalar_one()
    else:
        stmt = (
            sqlite_insert(museums_table)
            .values(name=name, city_id=city_id, visitors=visitors)
            .on_conflict_do_update(
                index_elements=["name"],
                set_={"city_id": city_id, "visitors": visitors},
            )
        )
        conn.execute(stmt)
        row = conn.execute(
            select(museums_table.c.id).where(museums_table.c.name == name)
        ).fetchone()
        return row[0]


def load_museums(museums_data: list[dict[str, Any]], engine: Engine) -> None:
    """Bulk-load museum data into the DB."""
    with engine.begin() as conn:
        for m in museums_data:
            city_id = _upsert_city(conn, engine, m["city"], m["country"], m.get("city_population"))
            _upsert_museum(conn, engine, m["name"], city_id, m["visitors"])
    logger.info("Loaded %d museums into database", len(museums_data))


def query_dataset(engine: Engine) -> pd.DataFrame:
    """Return a joined DataFrame of museums + city population for analysis."""
    query = text("""
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
    """)
    with engine.connect() as conn:
        return pd.read_sql_query(query, conn)
