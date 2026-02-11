"""Initial schema — raw tables, feature table, model registry.

Revision ID: 0001
Revises:
Create Date: 2026-02-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "museums_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("museum_name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text()),
        sa.Column("country", sa.Text()),
        sa.Column("annual_visitors", sa.BigInteger()),
        sa.Column("attendance_year", sa.Integer()),
        sa.Column("city_wikipedia_title", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "city_population_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("country", sa.Text()),
        sa.Column("city_wikipedia_title", sa.Text()),
        sa.Column("wikidata_item_id", sa.Text()),
        sa.Column("population", sa.BigInteger()),
        sa.Column("population_as_of", sa.Date()),
        sa.Column("source_url", sa.Text()),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "museum_city_features",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("museum_name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text()),
        sa.Column("country", sa.Text()),
        sa.Column("annual_visitors", sa.BigInteger()),
        sa.Column("attendance_year", sa.Integer()),
        sa.Column("population", sa.BigInteger()),
        sa.Column("population_as_of", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "model_registry",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("model_version", sa.String(64), nullable=False, unique=True),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("r2", sa.Float()),
        sa.Column("mae", sa.Float()),
        sa.Column("rmse", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("model_registry")
    op.drop_table("museum_city_features")
    op.drop_table("city_population_raw")
    op.drop_table("museums_raw")
