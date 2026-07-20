.PHONY: setup seed-db ingest-rag run verify docker-up

setup:
	python -m venv .venv
	.venv/Scripts/pip install -r requirements.txt

seed-db:
	.venv/Scripts/python scripts/seed_data.py

ingest-rag:
	.venv/Scripts/python scripts/ingest_schema.py

run:
	.venv/Scripts/uvicorn src.api.server:app --reload

verify:
	.venv/Scripts/python scripts/verify.py

docker-up:
	docker compose up --build
