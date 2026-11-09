# DocuSpace API

FastAPI service for managing projects and documents (**api → repositories + storage**).

Managed with **[uv](https://docs.astral.sh/uv/)** (venv, installs, lockfile).

## Quick start

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

cp .env.example .env
make install          # uv sync --all-groups
make up               # docker compose: db + localstack + api
curl -s localhost:8000/health
```

Local API (Postgres + LocalStack in Docker):

```bash
make dev
```

## Architecture & Code Structure Overview

DocuSpace keeps a flat, straightforward structure without unnecessary intermediate layers:

1. **API Layer (`src/app/api/`)** — Self-documenting FastAPI routes with colocated Pydantic request/response models (`health.py`, `auth.py`, `projects.py`, `documents.py`) and explicit `try ... except -> HTTPException` error mapping.
2. **Repositories & Storage (`src/app/repositories/`)** — `UserRepository`, `ProjectRepository`, `DocumentRepository`, and `S3Storage` / `InMemoryStorage` encapsulating database operations, permission checks, and S3 object storage.
3. **Root Modules (`src/app/`)** — `models.py` (all SQLAlchemy 2.0 ORM models), `database.py`, `config.py`, `security.py`, `errors.py` (plain domain exceptions), and `main.py`.

```text
src/app/
  api/            # FastAPI routes + colocated Pydantic schemas (health, auth, projects, documents)
  repositories/   # UserRepository, ProjectRepository, DocumentRepository, S3/in-memory storage
  config.py       # Settings (pydantic-settings)
  database.py     # SQLAlchemy engine & session factory
  errors.py       # Plain domain exceptions
  main.py         # FastAPI app factory & lifespan
  models.py       # SQLAlchemy 2.0 ORM models (users, projects, project_members, documents)
  security.py     # Password hashing (bcrypt) & JWT helpers
migrations/       # Alembic migrations
postman/          # Ready-to-import Postman collection
tests/            # Unit and PostgreSQL integration tests
```

## Make targets

| Target | Description |
| --- | --- |
| `make install` / `make sync` | `uv sync --all-groups` |
| `make lock` | Refresh `uv.lock` |
| `make up` | Docker Compose (db + localstack + api) |
| `make down` | Stop stack |
| `make dev` | Start DB + LocalStack in Docker |
| `make migrate` | Apply Alembic migrations (`uv run alembic upgrade head`) |
| `make lint` | ruff + mypy via `uv run` |
| `make test` | pytest via `uv run` |

---

# DocuSpace API Spec

### Scope
- User registration and JWT-based authentication (1-hour token lifetime).
- Lifecycle management of projects (creation, metadata updates, deletion, storage quota tracking).
- Role-based access control with two roles: **owner** (full control, deletion, invitations) and **participant** (view and modify project details and documents, cannot delete project or invite users).
- Management of project documents (`.pdf`, `.docx`) stored in AWS S3.
- Project sharing by inviting registered users (`login`) as project participants.

### Conventions
- **Authentication:** All business endpoints require `Authorization: Bearer <jwt_token>` issued by `POST /login` (valid for 1 hour).
- **Content Format:** All requests and responses use `application/json`, except document upload (`multipart/form-data`) and document download (binary file stream).
- **Error Format:** Error responses use standard FastAPI `{"detail": "..."}` messages with appropriate HTTP status codes.

### Endpoints Overview

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service liveness check |
| `GET` | `/ready` | Database readiness check (`SELECT 1`) |
| `POST` | `/auth` | Register a new user account (`login`, `password`, `repeat_password`) |
| `POST` | `/login` | Authenticate user and issue a 1-hour JWT |
| `POST` | `/projects` | Create a new project (creator becomes `owner`) |
| `GET` | `/projects` | List all projects accessible to the current user |
| `GET` | `/project/{project_id}/info` | Retrieve project details if the user has access |
| `PUT` | `/project/{project_id}/info` | Update project name and description |
| `DELETE` | `/project/{project_id}` | Delete a project and all its documents (`owner` only) |
| `GET` | `/project/{project_id}/documents` | List all documents attached to a project |
| `POST` | `/project/{project_id}/documents` | Upload one or more `.pdf` / `.docx` documents to a project |
| `GET` | `/document/{document_id}` | Download a document if the user has access to its project |
| `PUT` | `/document/{document_id}` | Update (replace) an existing document file |
| `DELETE` | `/document/{document_id}` | Delete a document from the project and S3 |
| `POST` | `/project/{project_id}/invite` | Grant `participant` access to a user by login (`owner` only) |

---

### `POST /auth`
Create a new user account using a unique `login` and matching password confirmation.

**Request:**
```json
{
  "login": "alex_dev",
  "password": "StrongPassword123!",
  "repeat_password": "StrongPassword123!"
}
```

**Response (`201 Created`):**
```json
{
  "id": 1,
  "login": "alex_dev",
  "created_at": "2026-11-02T14:00:00Z"
}
```

**Errors:**
- `400` Passwords do not match.
- `409` User with this `login` already exists.

---

### `POST /login`
Authenticate an existing user and return a signed JWT valid for 1 hour (`3600` seconds).

**Request:**
```json
{
  "login": "alex_dev",
  "password": "StrongPassword123!"
}
```

**Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:**
- `401` Invalid login or password.
- `422` Validation error (missing fields).

---

### `POST /projects`
Create a new project from the provided details and automatically assign the authenticated user as the project `owner`.

**Request:**
```json
{
  "name": "Q4 Architecture Review",
  "description": "Design documents and RFCs for the Q4 platform migration."
}
```

**Response (`201 Created`):**
```json
{
  "id": 1,
  "name": "Q4 Architecture Review",
  "description": "Design documents and RFCs for the Q4 platform migration.",
  "role": "owner",
  "total_size_bytes": 0,
  "created_at": "2026-11-02T14:05:00Z",
  "updated_at": "2026-11-02T14:05:00Z"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `422` Invalid project name or description.

---

### `GET /projects`
Retrieve all projects accessible to the authenticated user (as `owner` or `participant`).

**Response (`200 OK`):**
```json
[
  {
    "id": 1,
    "name": "Q4 Architecture Review",
    "description": "Design documents and RFCs for the Q4 platform migration.",
    "role": "owner",
    "total_size_bytes": 245760,
    "created_at": "2026-11-02T14:05:00Z",
    "updated_at": "2026-11-02T14:15:00Z"
  }
]
```

**Errors:**
- `401` Missing or expired JWT.

---

### `GET /project/{project_id}/info`
Retrieve details for a specific project if the authenticated user has access.

**Response (`200 OK`):**
```json
{
  "id": 1,
  "name": "Q4 Architecture Review",
  "description": "Design documents and RFCs for the Q4 platform migration.",
  "role": "participant",
  "total_size_bytes": 245760,
  "created_at": "2026-11-02T14:05:00Z",
  "updated_at": "2026-11-02T14:15:00Z"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` User has no access to this project.
- `404` Project not found.

---

### `PUT /project/{project_id}/info`
Update a project's `name` and `description` (accessible to both `owner` and `participant`) and return the updated project details.

**Request:**
```json
{
  "name": "Q4 Architecture Review (Final)",
  "description": "Approved RFCs and migration runbooks."
}
```

**Response (`200 OK`):**
```json
{
  "id": 1,
  "name": "Q4 Architecture Review (Final)",
  "description": "Approved RFCs and migration runbooks.",
  "role": "owner",
  "total_size_bytes": 245760,
  "created_at": "2026-11-02T14:05:00Z",
  "updated_at": "2026-11-02T14:30:00Z"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` User has no access to this project.
- `404` Project not found.
- `422` Invalid project details.

---

### `DELETE /project/{project_id}`
Permanently delete a project and remove all associated documents from PostgreSQL and AWS S3. Restricted to the project `owner`.

**Response (`200 OK`):**
```json
{
  "id": 1,
  "status": "deleted"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` Only the project `owner` can delete the project.
- `404` Project not found.

---

### `GET /project/{project_id}/documents`
Return all documents attached to the specified project.

**Response (`200 OK`):**
```json
[
  {
    "id": 1,
    "project_id": 1,
    "filename": "system_design.pdf",
    "content_type": "application/pdf",
    "size_bytes": 245760,
    "created_at": "2026-11-02T14:15:00Z",
    "updated_at": "2026-11-02T14:15:00Z"
  }
]
```

**Errors:**
- `401` Missing or expired JWT.
- `403` User has no access to the corresponding project.
- `404` Project not found.

---

### `POST /project/{project_id}/documents`
Upload one or multiple documents (`.pdf`, `.docx`) to a project via `multipart/form-data`. Accessible to `owner` and `participant`.

**Request (`multipart/form-data`):**
- `files`: one or more `.pdf` or `.docx` binary files.

**Response (`201 Created`):**
```json
[
  {
    "id": 1,
    "project_id": 1,
    "filename": "system_design.pdf",
    "content_type": "application/pdf",
    "size_bytes": 245760,
    "created_at": "2026-11-02T14:15:00Z",
    "updated_at": "2026-11-02T14:15:00Z"
  }
]
```

**Errors:**
- `400` Empty upload or duplicate filenames in the same upload request.
- `401` Missing or expired JWT.
- `403` User has no access to the corresponding project.
- `404` Project not found.
- `409` A document with the same `filename` already exists in this project.
- `413` File size or total project storage quota exceeded.
- `415` Unsupported file type (only `.pdf` and `.docx` allowed).

---

### `GET /document/{document_id}`
Download a specific document if the authenticated user has access to its parent project.

**Response (`200 OK`):**
- Headers:
  - `Content-Type: application/pdf` (or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
  - `Content-Disposition: attachment; filename="system_design.pdf"`
- Body: binary file stream.

**Errors:**
- `401` Missing or expired JWT.
- `403` User has no access to the corresponding project.
- `404` Document not found.

---

### `PUT /document/{document_id}`
Update (replace) the binary content of an existing document (`.pdf` or `.docx`). Accessible to `owner` and `participant` of the parent project.

**Request (`multipart/form-data`):**
- `file`: replacement `.pdf` or `.docx` file.

**Response (`200 OK`):**
```json
{
  "id": 1,
  "project_id": 1,
  "filename": "system_design.pdf",
  "content_type": "application/pdf",
  "size_bytes": 312400,
  "created_at": "2026-11-02T14:15:00Z",
  "updated_at": "2026-11-02T15:00:00Z"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` User has no access to the corresponding project.
- `404` Document not found.
- `413` Project storage quota exceeded.
- `415` Unsupported file type.

---

### `DELETE /document/{document_id}`
Delete a document record and remove its object from AWS S3. Accessible to `owner` and `participant` of the parent project.

**Response (`200 OK`):**
```json
{
  "id": 1,
  "status": "deleted"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` User has no access to the corresponding project.
- `404` Document not found.

---

### `POST /project/{project_id}/invite?user={login}`
Grant `participant` permissions on the project to another registered user identified by `login`. Restricted to the project `owner`.

**Response (`200 OK`):**
```json
{
  "project_id": 1,
  "invited_user": "maria_qa",
  "role": "participant"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` Forbidden (only the project `owner` can invite users).
- `404` Project or target user not found.
- `409` User is already a member of the project.
