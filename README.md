# Projects API

Layered FastAPI service: **api → services → repositories**.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make up
curl -s localhost:8000/health
```

Local API (Postgres in Docker):

```bash
make dev
```

## Layout

```text
src/app/
  api/            # routers, schemas, dependencies
  services/       # business logic
  repositories/   # data access
  models/         # ORM / data models
  core/           # config
  main.py         # FastAPI app factory
tests/
```

## Make targets

| Target | Description |
| --- | --- |
| `make install` | Create venv and install deps |
| `make up` | Docker Compose (db + api) |
| `make down` | Stop stack |
| `make dev` / `make local` | DB in Docker, API with reload on host |
| `make lint` | ruff + mypy |
| `make test` | pytest |
