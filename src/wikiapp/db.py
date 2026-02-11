"""Database layer — SQLAlchemy engine, sessions, and Alembic migrations.

Supports PostgreSQL (Docker / production) and SQLite (local dev / tests).
Backend is selected via DATABASE_URL env var; defaults to SQLite.

For tests, call ``init_db_tables(engine)`` which runs ``metadata.create_all``
directly (no Alembic needed, works with in-memory SQLite).

For production, call ``migrate_db()`` which runs Alembic migrations.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from wikiapp.config import settings

logger = logging.getLogger(__name__)

metadata = MetaData()

# ------------------------------------------------------------------
# Schema declaration (used by both create_all and as documentation;
# Alembic migration is the source of truth for production).
# ------------------------------------------------------------------

museums_raw = Table(
    "museums_raw", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("museum_name", Text, nullable=False),
    Column("city", Text),
    Column("country", Text),
    Column("annual_visitors", BigInteger),
    Column("attendance_year", Integer),
    Column("city_wikipedia_title", Text),
    Column("source_url", Text),
    Column("ingested_at", DateTime(timezone=True), server_default=func.current_timestamp()),
)

city_population_raw = Table(
    "city_population_raw", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("city", Text, nullable=False),
    Column("country", Text),
    Column("city_wikipedia_title", Text),
    Column("wikidata_item_id", Text),
    Column("population", BigInteger),
    Column("population_as_of", Date),
    Column("source_url", Text),
    Column("ingested_at", DateTime(timezone=True), server_default=func.current_timestamp()),
)

museum_city_features = Table(
    "museum_city_features", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("museum_name", Text, nullable=False),
    Column("city", Text),
    Column("country", Text),
    Column("annual_visitors", BigInteger),
    Column("attendance_year", Integer),
    Column("population", BigInteger),
    Column("population_as_of", Date),
    Column("created_at", DateTime(timezone=True), server_default=func.current_timestamp()),
)

model_registry = Table(
    "model_registry", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("model_version", String(64), nullable=False, unique=True),
    Column("artifact_path", Text, nullable=False),
    Column("r2", Float),
    Column("mae", Float),
    Column("rmse", Float),
    Column("created_at", DateTime(timezone=True), server_default=func.current_timestamp()),
)

# ------------------------------------------------------------------
# Engine / session helpers
# ------------------------------------------------------------------

_engine: Engine | None = None


def get_engine(url: str | None = None) -> Engine:
    """Return a (cached) engine.  Tests can pass an explicit URL."""
    global _engine
    if url:
        return create_engine(url, echo=False)
    if _engine is None:
        _engine = create_engine(settings.database_url, echo=False)
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker:
    engine = engine or get_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session(engine: Engine | None = None):
    """Yield a SQLAlchemy session with auto-commit / rollback."""
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ------------------------------------------------------------------
# Schema management
# ------------------------------------------------------------------

def init_db_tables(engine: Engine) -> None:
    """Create all tables directly (for tests / SQLite local dev)."""
    metadata.create_all(engine)


def migrate_db(database_url: str | None = None) -> None:
    """Run Alembic migrations for PostgreSQL, or create_all for SQLite."""
    url = database_url or settings.database_url
    engine = create_engine(url, echo=False)

    # For SQLite, just create tables directly
    if make_url(url).drivername.startswith("sqlite"):
        metadata.create_all(engine)
        engine.dispose()
        return

    _ensure_pg_database(url)

    project_root = Path(__file__).resolve().parents[2]
    ini_path = project_root / "alembic.ini"
    if not ini_path.exists():
        logger.warning("alembic.ini not found, falling back to create_all")
        metadata.create_all(engine)
        engine.dispose()
        return

    from alembic import command
    from alembic.config import Config

    config = Config(str(ini_path))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine.dispose()


def _ensure_pg_database(database_url: str) -> None:
    """Create the target PostgreSQL database if it doesn't exist."""
    url = make_url(database_url)
    target_db = url.database
    if not target_db:
        return
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_db},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    finally:
        admin_engine.dispose()
