.PHONY: install lint format typecheck test test-integration test-eval quick-gate up down

# All backend commands run through uv against the backend project.
UV := uv --directory backend

install:
	$(UV) sync

lint:
	$(UV) run ruff check

format:
	$(UV) run ruff format

typecheck:
	$(UV) run mypy src

test:
	$(UV) run pytest tests/unit

test-integration:
	$(UV) run pytest -m integration

test-eval:
	$(UV) run pytest -m eval

# Mirrors the CI quick-gate, in the same order, so green here means green in CI.
quick-gate:
	$(UV) run ruff check
	$(UV) run ruff format --check
	$(UV) run mypy src
	$(UV) run pytest tests/unit

# Local data stack: Supabase (Postgres + Auth) and Weaviate.
up:
	supabase start
	docker compose up -d

down:
	docker compose down
	supabase stop
