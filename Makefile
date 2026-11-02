.PHONY: help install sync up down test lint format typecheck migrate dev local lock

# Prefer uv from PATH; fall back to ~/.local/bin (default install location)
UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
HOST ?= 127.0.0.1
PORT ?= 8000

help:
	@echo "Targets (uv-based):"
	@echo "  make install / sync   Create .venv and install deps + project (incl. dev group)"
	@echo "  make lock             Refresh uv.lock from pyproject.toml"
	@echo "  make up               Build and start db + api (Docker Compose)"
	@echo "  make down             Stop Docker Compose stack"
	@echo "  make dev / local      DB in Docker; API on host with --reload"
	@echo "  make migrate          Apply Alembic migrations (alembic upgrade head)"
	@echo "  make lint             ruff check + format --check + mypy --strict"
	@echo "  make format           Auto-fix and format with ruff"
	@echo "  make typecheck        mypy --strict only"
	@echo "  make test             Run pytest"

install sync:
	$(UV) sync --all-groups

lock:
	$(UV) lock

up:
	docker compose up --build -d

down:
	docker compose down

lint:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests
	$(UV) run mypy --strict src tests

format:
	$(UV) run ruff check --fix src tests
	$(UV) run ruff format src tests

typecheck:
	$(UV) run mypy --strict src tests

test:
	$(UV) run pytest

migrate:
	$(UV) run alembic upgrade head

# DB in Docker; API on host via uv-managed venv
dev:
	docker compose up -d db
	$(UV) run alembic upgrade head
	$(UV) run uvicorn app.main:create_app --factory --reload --host $(HOST) --port $(PORT)

local: dev
