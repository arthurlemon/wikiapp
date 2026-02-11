"""CLI with subcommands.

Subcommands:
  migrate-db      Run Alembic schema migrations
  run-etl         Fetch museums + enrich city population
  build-features  Join raw tables into the feature table
  train           Train + persist a linear regression model
  run-all         Run the full pipeline end-to-end
"""

from __future__ import annotations

import argparse
import logging

from wikiapp.db import migrate_db
from wikiapp.services.etl import enrich_population, get_distinct_city_titles, ingest_museums
from wikiapp.services.training import train
from wikiapp.services.transform import build_feature_table


def _build_parser() -> argparse.ArgumentParser:
    # Shared flags available to every subcommand
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true")

    p = argparse.ArgumentParser(description="wikiapp CLI", parents=[common])
    sub = p.add_subparsers(dest="command")
    sub.default = "run-all"

    for name in ("migrate-db", "run-etl", "build-features", "train", "run-all"):
        sub.add_parser(name, parents=[common])
    return p


# ---- pipeline steps ----

def _run_etl() -> dict[str, int]:
    museums = ingest_museums()
    titles = get_distinct_city_titles()
    cities = enrich_population(titles)
    return {"museums": museums, "cities": cities}


def _run_features() -> int:
    return build_feature_table()


def _run_train() -> dict:
    r = train()
    return {"model_version": r.model_version, "r2": r.r2, "rmse": r.rmse}


def _run_all() -> dict:
    etl = _run_etl()
    features = _run_features()
    model = _run_train()
    return {"etl": etl, "features": features, "model": model}


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    cmd = args.command or "run-all"
    migrate_db()

    if cmd == "migrate-db":
        return

    runners = {
        "run-etl": _run_etl,
        "build-features": _run_features,
        "train": _run_train,
        "run-all": _run_all,
    }
    result = runners[cmd]()
    logging.info("Result: %s", result)


if __name__ == "__main__":
    main()
