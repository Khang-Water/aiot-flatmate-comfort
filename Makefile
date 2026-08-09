.PHONY: install dev check smoke api web

install:
	cd backend && uv sync --group dev --extra speech
	npm --prefix frontend install

dev:
	bash scripts/dev.sh

check:
	cd backend && uv run --group dev --extra speech ruff check app tests
	cd backend && uv run --group dev --extra speech pytest
	npm --prefix frontend run check
	npm --prefix frontend run build

smoke:
	npm --prefix frontend run smoke

api:
	cd backend && uv run --extra speech uvicorn app.main:app --reload --timeout-graceful-shutdown 2 --host 127.0.0.1 --port 8000

web:
	npm --prefix frontend run dev
