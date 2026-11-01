.PHONY: help install up down test lint format typecheck dev local

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
HOST ?= 127.0.0.1
PORT ?= 8000

help:
	@echo "Targets:"
	@echo "  make install     Create .venv and install package with [dev] extras"
	@echo "  make up          Build and start db + api (Docker Compose)"
	@echo "  make down        Stop Docker Compose stack"
	@echo "  make dev         Start db in Docker; run API locally with --reload"
	@echo "  make local       Alias for make dev"
	@echo "  make lint        ruff check + format --check + mypy --strict"
	@echo "  make format      Auto-fix and format with ruff"
	@echo "  make typecheck   mypy --strict only"
	@echo "  make test        Run pytest"

install:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e ".[dev]"

up:
	docker compose up --build -d

down:
	docker compose down

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests
	$(PYTHON) -m mypy --strict src tests

format:
	$(PYTHON) -m ruff check --fix src tests
	$(PYTHON) -m ruff format src tests

typecheck:
	$(PYTHON) -m mypy --strict src tests

test:
	$(PYTHON) -m pytest

# DB in Docker
dev:
	docker compose up -d db

local: dev
