# Projects API

Layered FastAPI service: **api → services → repositories**.

Managed with **[uv](https://docs.astral.sh/uv/)** (venv, installs, lockfile).

## Quick start

```bash
# install uv once: https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

cp .env.example .env
make install          # uv sync --all-groups  → creates .venv + installs deps
make up               # docker compose: db + api
curl -s localhost:8000/health
```

Local API (Postgres in Docker, API with reload):

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
| `make install` / `make sync` | `uv sync --all-groups` |
| `make lock` | Refresh `uv.lock` |
| `make up` | Docker Compose (db + api) |
| `make down` | Stop stack |
| `make dev` | DB in Docker, API with reload (`uv run uvicorn …`) |
| `make lint` | ruff + mypy via `uv run` |
| `make test` | pytest via `uv run` |
