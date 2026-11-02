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

---

# DocuSpace API Spec

### Scope
- User registration with separate `login` (username) and `email`, email verification flow, and JWT-based authentication (1-hour token lifetime).
- Lifecycle management of projects (creation, metadata updates, deletion, storage quota tracking).
- Role-based access control with two roles: **owner** (full control, deletion, invitations) and **participant** (view and modify project details and documents, cannot delete project or invite users).
- Management of project documents (`.pdf`, `.docx`) stored in AWS S3 with full document versioning (`v1`, `v2`, …), unique filenames per project, and asynchronous size calculation/quota enforcement via AWS Lambda.
- Project sharing via direct user invitation (`login`) and optional email join links (`email`) with signed tokens.

### Conventions
- **Authentication:** All business endpoints require `Authorization: Bearer <jwt_token>` issued by `POST /login` (valid for 1 hour).
- **Email Verification (side feature):** Registration sends a verification link (`GET /auth/verify?token=...`) to the user's email; users must verify their email before logging in.
- **Content Format:** All requests and responses use `application/json`, except document upload (`multipart/form-data`) and document download (binary file stream).
- **Document Uniqueness & Versioning (side feature):**
  - Within a single project, `filename` is unique (`UNIQUE(project_id, filename)`).
  - S3 keys never use raw filenames; objects are stored at `projects/{project_id}/documents/{document_id}/v{version}`.
  - Uploading a new file via `POST /project/{project_id}/documents` creates `version = 1` (or returns `409 Conflict` if that filename already exists in the project).
  - Updating a document via `PUT /document/{document_id}` creates a new immutable version (`v2`, `v3`, …) and increments `current_version`. The uploaded file must keep the same extension as the original document (`.pdf` → `.pdf`, `.docx` → `.docx`).
- **Pagination & Filtering (side feature):** List endpoints (`GET /projects`, `GET /project/{project_id}/documents`) support optional query parameters `limit` (default `20`, max `100`), `offset` (default `0`), and `search` (substring match on name/filename).
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
| `POST` | `/auth` | Register a new user account (`login`, `email`, `password`, `repeat_password`) |
| `GET` | `/auth/verify` | *(Side feature)* Verify a user's email address via signed token |
| `POST` | `/login` | Authenticate user (by `login` or `email`) and issue a 1-hour JWT |
| `POST` | `/projects` | Create a new project (creator becomes `owner`) |
| `GET` | `/projects` | List all projects accessible to the current user (details + documents, paginated) |
| `GET` | `/project/{project_id}/info` | Retrieve project details and member list if the user has access |
| `PUT` | `/project/{project_id}/info` | Update project name and description |
| `DELETE` | `/project/{project_id}` | Delete a project and all its documents (`owner` only) |
| `GET` | `/project/{project_id}/documents` | List all documents attached to a project |
| `POST` | `/project/{project_id}/documents` | Upload one or more new `.pdf` / `.docx` documents (`v1`) |
| `GET` | `/document/{document_id}` | Download a document (latest version by default, or `?version={n}`) |
| `PUT` | `/document/{document_id}` | Upload a new version (`v2`, `v3`, …) of an existing document |
| `GET` | `/document/{document_id}/versions` | *(Side feature)* List version history for a document |
| `DELETE` | `/document/{document_id}` | Delete a document and all of its versions from the project and S3 |
| `POST` | `/project/{project_id}/invite` | Grant `participant` access to a user by login (`owner` only) |
| `DELETE` | `/project/{project_id}/members/{login}` | *(Side feature)* Revoke a participant's access to the project (`owner` only) |
| `GET` | `/project/{project_id}/share` | *(Optional)* Send an email with a hashed `/join` link (`owner` only) |
| `GET` | `/join` | *(Optional)* Accept a project invitation via a signed token from email |

---

### `POST /auth`
Create a new user account using a unique `login` (username), a unique `email`, and matching password confirmation. Sends a signed verification link (`GET /auth/verify?token=...`) to the user's email address.

**Request:**
```json
{
  "login": "alex_dev",
  "email": "alex@example.com",
  "password": "StrongPassword123!",
  "repeat_password": "StrongPassword123!"
}
```

**Response (`201 Created`):**
```json
{
  "id": "b3f1c2d0-8e41-4c7a-9b1f-12c9f7e10a11",
  "login": "alex_dev",
  "email": "alex@example.com",
  "is_verified": false,
  "created_at": "2026-11-02T14:00:00Z"
}
```

**Errors:**
- `400` Passwords do not match or invalid login/email/password format.
- `409` User with this `login` or `email` already exists.

---

### `GET /auth/verify?token={verification_token}` *(Side feature)*
Verify a newly registered user's email address using the signed token sent during `POST /auth`.

**Response (`200 OK`):**
```json
{
  "id": "b3f1c2d0-8e41-4c7a-9b1f-12c9f7e10a11",
  "login": "alex_dev",
  "email": "alex@example.com",
  "is_verified": true,
  "status": "email_verified"
}
```

**Errors:**
- `400` Invalid, expired, or already used verification token.
- `404` User not found.

---

### `POST /login`
Authenticate an existing user (accepts either `login` username or `email` in the `login` field) and return a signed JWT valid for 1 hour (`3600` seconds).

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
- `401` Invalid login/email or password.
- `403` Email address has not been verified yet.
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
Retrieve all projects accessible to the authenticated user (as `owner` or `participant`), including project details and attached documents. Supports optional pagination (`limit`, `offset`), role filter (`role=owner|participant`), and name search (`search`).

**Query parameters (optional):**
- `limit=20&offset=0&search=Architecture&role=owner`

**Response (`200 OK`):**
```json
{
  "items": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "name": "Q4 Architecture Review",
      "description": "Design documents and RFCs for the Q4 platform migration.",
      "role": "owner",
      "total_size_bytes": 245760,
      "created_at": "2026-11-02T14:05:00Z",
      "updated_at": "2026-11-02T14:15:00Z",
      "documents": [
        {
          "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
          "filename": "system_design.pdf",
          "content_type": "application/pdf",
          "current_version": 1,
          "size_bytes": 245760,
          "uploaded_at": "2026-11-02T14:15:00Z"
        }
      ]
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Errors:**
- `401` Missing or expired JWT.

---

### `GET /project/{project_id}/info`
Retrieve metadata, quota usage, and the member list for a specific project if the authenticated user has access.

**Response (`200 OK`):**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "name": "Q4 Architecture Review",
  "description": "Design documents and RFCs for the Q4 platform migration.",
  "role": "participant",
  "total_size_bytes": 245760,
  "max_size_bytes": 104857600,
  "members": [
    {
      "login": "alex_dev",
      "role": "owner"
    },
    {
      "login": "maria_qa",
      "role": "participant"
    }
  ],
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
List all documents attached to the specified project (showing each document's active `current_version`). Supports optional `limit`, `offset`, and `search` query parameters.

**Response (`200 OK`):**
```json
{
  "items": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "filename": "system_design.pdf",
      "content_type": "application/pdf",
      "current_version": 2,
      "size_bytes": 312400,
      "uploaded_by": "alex_dev",
      "uploaded_at": "2026-11-02T15:00:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Errors:**
- `401` Missing or expired JWT.
- `404` Project not found or user does not have access.

---

### `POST /project/{project_id}/documents`
Upload one or multiple new documents (`.pdf`, `.docx`) to a project via `multipart/form-data`. Accessible to `owner` and `participant`. Each new document is initialized at `current_version = 1` and stored in S3 under `projects/{project_id}/documents/{document_id}/v1`. Filenames must be unique within the project.

**Request (`multipart/form-data`):**
- `files`: one or more `.pdf` or `.docx` binary files (filenames within the batch must be unique).

**Response (`201 Created`):**
```json
{
  "uploaded": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "filename": "system_design.pdf",
      "content_type": "application/pdf",
      "current_version": 1,
      "size_bytes": 245760,
      "uploaded_at": "2026-11-02T14:15:00Z"
    }
  ]
}
```

**Errors:**
- `400` Unsupported file type (only `.pdf` and `.docx` allowed) or duplicate filenames within the same upload request.
- `401` Missing or expired JWT.
- `404` Project not found or user does not have access.
- `409` A document with the same `filename` already exists in this project (use `PUT /document/{document_id}` to upload a new version).
- `413` File size or total project storage quota exceeded.

---

### `GET /document/{document_id}`
Download a specific document if the authenticated user has access to its parent project. Downloads the latest version (`current_version`) by default, or a specific historical version when `?version={n}` is provided.

**Query parameters (optional):**
- `version=1` — specific version number to download (defaults to `current_version`).

**Response (`200 OK`):**
- Headers:
  - `Content-Type: application/pdf` (or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
  - `Content-Disposition: attachment; filename="system_design.pdf"`
  - `X-Document-Version: 2`
- Body: binary file stream.

**Errors:**
- `401` Missing or expired JWT.
- `404` Document (or requested version) not found, or user does not have access to the parent project.

---

### `PUT /document/{document_id}`
Upload a new version (`v2`, `v3`, …) of an existing document (`.pdf` or `.docx`). Accessible to `owner` and `participant` of the parent project. The replacement file must have the same extension as the existing document. Stores the new object in S3 under `projects/{project_id}/documents/{document_id}/v{new_version}` and increments `current_version`.

**Request (`multipart/form-data`):**
- `file`: new `.pdf` or `.docx` file version (matching the original document's extension).

**Response (`200 OK`):**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "filename": "system_design.pdf",
  "content_type": "application/pdf",
  "current_version": 2,
  "size_bytes": 312400,
  "updated_at": "2026-11-02T15:00:00Z"
}
```

**Errors:**
- `400` Unsupported file format or file extension does not match the original document.
- `401` Missing or expired JWT.
- `404` Document not found or user does not have access.
- `413` Project storage quota exceeded.

---

### `GET /document/{document_id}/versions` *(Side feature)*
Retrieve the full version history of a document if the authenticated user has access to its parent project.

**Response (`200 OK`):**
```json
{
  "document_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "filename": "system_design.pdf",
  "current_version": 2,
  "versions": [
    {
      "version": 2,
      "size_bytes": 312400,
      "uploaded_by": "alex_dev",
      "uploaded_at": "2026-11-02T15:00:00Z"
    },
    {
      "version": 1,
      "size_bytes": 245760,
      "uploaded_by": "alex_dev",
      "uploaded_at": "2026-11-02T14:15:00Z"
    }
  ]
}
```

**Errors:**
- `401` Missing or expired JWT.
- `404` Document not found or user does not have access.

---

### `DELETE /document/{document_id}`
Delete a document record and remove all of its stored versions from AWS S3. Accessible to `owner` and `participant` of the parent project.

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

---

### `DELETE /project/{project_id}/members/{login}` *(Side feature)*
Revoke a `participant` user's access to the project. Restricted to the project `owner` (the `owner` cannot remove themselves).

**Response (`200 OK`):**
```json
{
  "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "removed_user": "maria_qa",
  "status": "member_removed"
}
```

**Errors:**
- `400` Cannot remove the project `owner`.
- `401` Missing or expired JWT.
- `403` Forbidden (only the project `owner` can remove members).
- `404` Project or member not found.

---

### `GET /project/{project_id}/share?with={email}` *(Optional)*
Generate a signed, expiring invitation token and send a `GET /join?token=...` link to the specified email address. Restricted to the project `owner`.

**Response (`200 OK`):**
```json
{
  "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "recipient_email": "teammate@example.com",
  "expires_in": 86400,
  "status": "invitation_sent"
}
```

**Errors:**
- `401` Missing or expired JWT.
- `403` Forbidden (only the project `owner` can share the project).
- `404` Project not found.
- `422` Invalid email address.

---

### `GET /join?token={hashed_token}` *(Optional)*
Validate the single-use invitation token from the email link, verify that the authenticated user's verified `email` matches the invitation's `recipient_email`, and grant `participant` access.

**Response (`200 OK`):**
```json
{
  "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "name": "Q4 Architecture Review",
  "role": "participant",
  "status": "joined"
}
```

**Errors:**
- `400` Invalid, expired, or already used invitation token.
- `401` Missing or expired JWT.
- `403` Authenticated user's email does not match the invitation recipient email.
- `409` User is already a member of the project.
