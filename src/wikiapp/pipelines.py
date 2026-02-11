"""Optional Prefect flow definitions.

Only imported when the user passes --orchestrate to the CLI.
Requires: pip install wikiapp[orchestration]
"""

from __future__ import annotations

from prefect import flow, task

from wikiapp.db import migrate_db
from wikiapp.etl import enrich_population, get_distinct_city_titles, ingest_museums
from wikiapp.train import train
from wikiapp.transform import build_feature_table


@task
def init_db_task() -> None:
    migrate_db()


@task
def ingest_task() -> int:
    return ingest_museums()


@task
def enrich_task() -> int:
    titles = get_distinct_city_titles()
    return enrich_population(titles)


@task
def transform_task() -> int:
    return build_feature_table()


@task
def train_task() -> dict:
    result = train()
    return {"model_version": result.model_version, "r2": result.r2}


@flow(name="wikiapp-etl")
def etl_flow() -> dict[str, int]:
    init_db_task()
    museums = ingest_task()
    cities = enrich_task()
    return {"museums": museums, "cities": cities}


@flow(name="wikiapp-features")
def feature_flow() -> int:
    init_db_task()
    return transform_task()


@flow(name="wikiapp-train")
def train_flow() -> dict:
    init_db_task()
    return train_task()


@flow(name="wikiapp-full")
def full_flow() -> dict:
    etl = etl_flow()
    features = feature_flow()
    model = train_flow()
    return {"etl": etl, "features": features, "model": model}
