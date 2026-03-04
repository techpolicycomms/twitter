.PHONY: up down dev init scrape analyze digest linkedin newsletter

up:
	docker compose up -d

down:
	docker compose down

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

init:
	python scripts/init_db.py

scrape:
	python scripts/run_scrape.py

scrape-source:
	python scripts/run_scrape.py --source $(SOURCE)

digest:
	python scripts/generate_report.py digest

linkedin:
	python scripts/generate_report.py linkedin

newsletter:
	python scripts/generate_report.py newsletter

install:
	pip install -r requirements.txt
