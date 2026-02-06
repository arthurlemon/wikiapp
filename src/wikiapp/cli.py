"""CLI entry point: fetch data, build DB, run regression."""

from __future__ import annotations

import argparse
import logging
import sys

from wikiapp import db, model, population, scraper


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Museum visitor vs city population analysis"
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL (default: DATABASE_URL env var or sqlite:///data/museums.db)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # 1. Fetch museum data
    logging.info("Fetching museum data from Wikipedia...")
    museums = scraper.fetch_museums_from_wikipedia()
    if not museums:
        logging.error("No museum data retrieved. Exiting.")
        sys.exit(1)
    logging.info("Retrieved %d museums with >= 2M visitors", len(museums))

    # 2. Enrich with city population
    logging.info("Enriching with city population data...")
    museums = population.enrich_museums_with_population(museums)

    # 3. Store in database
    engine = db.get_engine(args.database_url)
    logging.info("Building database (%s)...", engine.url.drivername)
    db.init_db(engine)
    db.load_museums(museums, engine)

    # 4. Query and run regression
    df = db.query_dataset(engine)
    engine.dispose()

    if df.empty:
        logging.error("No data with population info available for regression.")
        sys.exit(1)

    logging.info("Running linear regression on %d data points...", len(df))
    result = model.run_regression(df)
    print("\n" + model.summary(result))


if __name__ == "__main__":
    main()
