"""Centralised settings resolved from environment variables.

Requires PostgreSQL — set DATABASE_URL or individual POSTGRES_* vars.
Docker Compose provides these automatically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _default_database_url() -> str:
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    # Allow composing from individual PG vars (Docker Compose pattern)
    user = os.environ.get("POSTGRES_USER", "wikiapp")
    pw = os.environ.get("POSTGRES_PASSWORD", "wikiapp")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "museums")
    return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=_default_database_url)
    artifacts_dir: str = field(default_factory=lambda: os.environ.get("ARTIFACTS_DIR", "./artifacts"))
    wikipedia_user_agent: str = field(
        default_factory=lambda: os.environ.get(
            "WIKIPEDIA_USER_AGENT", "wikiapp/0.3 (museum-data-pipeline)"
        )
    )
    wikidata_token: str | None = field(
        default_factory=lambda: os.environ.get("WIKIDATA_TOKEN")
    )
    visitor_threshold: int = 2_000_000


settings = Settings()
