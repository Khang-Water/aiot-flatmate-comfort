.PHONY: install dev check smoke api web

install:
	cd backend && uv sync --group dev
	npm --prefix frontend install

dev:
	bash scripts/dev.sh

check:
	cd backend && uv run ruff check app tests
	cd backend && uv run pytest
	npm --prefix frontend run check
	npm --prefix frontend run build

smoke:
	npm --prefix frontend run smoke

api:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web:
	npm --prefix frontend run dev
