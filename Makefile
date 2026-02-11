.PHONY: setup migrate etl features train run-all api notebook test clean docker-up docker-down

# ---- Local development (SQLite, no Docker) ----

setup:
	pip install -e ".[dev]"

migrate:
	wikiapp migrate-db

etl:
	wikiapp run-etl

features:
	wikiapp build-features

train:
	wikiapp train

run-all:
	wikiapp run-all

api:
	uvicorn wikiapp.api:app --host 0.0.0.0 --port 8000 --reload

notebook:
	jupyter notebook notebooks/ --port 8888

test:
	python -m pytest -v

clean:
	rm -rf data/ artifacts/ .pytest_cache/ __pycache__/

# ---- Docker (PostgreSQL) ----

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
