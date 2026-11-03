# DocuSpace API

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
  api/            # routes and request/response schemas defined together
  services/       # business logic
  repositories/   # data access
  models/         # ORM / data models
  core/           # config, database, errors, security
  main.py         # FastAPI app factory
migrations/       # Alembic migrations
tests/
```

## Make targets

| Target | Description |
| --- | --- |
| `make install` / `make sync` | `uv sync --all-groups` |
| `make lock` | Refresh `uv.lock` |
| `make up` | Docker Compose (db + api) |
| `make down` | Stop stack |
| `make dev` | DB in Docker, migrations + API with reload (`uv run uvicorn …`) |
| `make migrate` | Apply Alembic migrations (`uv run alembic upgrade head`) |
| `make lint` | ruff + mypy via `uv run` |
| `make test` | pytest via `uv run` |

---

# DocuSpace API Spec

### Scope
- User registration and JWT-based authentication (1-hour token lifetime).
- Lifecycle management of projects (creation, metadata updates, deletion, storage quota tracking).
- Role-based access control with two roles: **owner** (full control, deletion, invitations) and **participant** (view and modify project details and documents, cannot delete project or invite users).
- Management of project documents (`.pdf`, `.docx`) stored in AWS S3 with asynchronous size calculation and quota enforcement via AWS Lambda.
- Project sharing by inviting registered users (`login`) as project participants.

### Conventions
- **Authentication:** All business endpoints require `Authorization: Bearer <jwt_token>` issued by `POST /login` (valid for 1 hour).
- **Content Format:** All requests and responses use `application/json`, except document upload (`multipart/form-data`) and document download (binary file stream).
- **Unified Error Format:** All error responses (`4xx` / `5xx`) return a standardized JSON envelope:
  ```json
  {
    "error": {
      "code": "PROJECT_NOT_FOUND",
      "message": "Project not found or user does not have access."
    }
  }
  ```

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
  "id": "b3f1c2d0-8e41-4c7a-9b1f-12c9f7e10a11",
  "login": "alex_dev",
  "created_at": "2026-11-02T14:00:00Z"
}
```

**Errors:**
- `400` Passwords do not match or invalid login/password format.
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
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
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
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
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
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
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
- `404` Project not found or user does not have access.

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
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
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
- `404` Project not found or user does not have access.
- `422` Invalid project details.

---

### `DELETE /project/{project_id}`
Permanently delete a project and remove all associated documents from PostgreSQL and AWS S3. Restricted to the project `owner`.

**Response (`200 OK`):**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "deleted"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` Forbidden (only the project `owner` can delete the project).
- `404` Project not found or user does not have access.

---

### `GET /project/{project_id}/documents`
Return all documents attached to the specified project.

**Response (`200 OK`):**
```json
[
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
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
- `404` Project not found or user does not have access.

---

### `POST /project/{project_id}/documents`
Upload one or multiple documents (`.pdf`, `.docx`) to a project via `multipart/form-data`. Accessible to `owner` and `participant`. Filenames must be unique within the project.

**Request (`multipart/form-data`):**
- `files`: one or more `.pdf` or `.docx` binary files.

**Response (`201 Created`):**
```json
[
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "filename": "system_design.pdf",
    "content_type": "application/pdf",
    "size_bytes": 245760,
    "created_at": "2026-11-02T14:15:00Z",
    "updated_at": "2026-11-02T14:15:00Z"
  }
]
```

**Errors:**
- `400` Unsupported file type (only `.pdf` and `.docx` allowed) or duplicate filenames in the same upload request.
- `401` Missing or expired JWT.
- `404` Project not found or user does not have access.
- `409` A document with the same `filename` already exists in this project.
- `413` File size or total project storage quota exceeded.

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
- `404` Document not found or user does not have access to the parent project.

---

### `PUT /document/{document_id}`
Update (replace) the binary content of an existing document (`.pdf` or `.docx`). Accessible to `owner` and `participant` of the parent project.

**Request (`multipart/form-data`):**
- `file`: replacement `.pdf` or `.docx` file.

**Response (`200 OK`):**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "filename": "system_design.pdf",
  "content_type": "application/pdf",
  "size_bytes": 312400,
  "created_at": "2026-11-02T14:15:00Z",
  "updated_at": "2026-11-02T15:00:00Z"
}
```

**Errors:**
- `400` Unsupported file format.
- `401` Missing or expired JWT.
- `404` Document not found or user does not have access.
- `413` Project storage quota exceeded.

---

### `DELETE /document/{document_id}`
Delete a document record and remove its object from AWS S3. Accessible to `owner` and `participant` of the parent project.

**Response (`200 OK`):**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "deleted"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `404` Document not found or user does not have access.

---

### `POST /project/{project_id}/invite?user={login}`
Grant `participant` permissions on the project to another registered user identified by `login`. Restricted to the project `owner`.

**Response (`200 OK`):**
```json
{
  "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "invited_user": "maria_qa",
  "role": "participant"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` Forbidden (only the project `owner` can invite users).
- `404` Project or target user not found.
- `409` User is already a member of the project.
