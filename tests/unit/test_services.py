import uuid
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.models.document import Document
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User
from app.repositories.document import DocumentRepositoryProtocol
from app.repositories.project import ProjectRepositoryProtocol
from app.repositories.user import UserRepositoryProtocol
from app.services.document import DocumentService, FileUploadPayload
from app.services.project import ProjectService
from app.services.storage import InMemoryStorageService


class FakeUserRepo(UserRepositoryProtocol):
    def __init__(self) -> None:
        self.users_by_id: dict[uuid.UUID, User] = {}
        self.users_by_login: dict[str, User] = {}

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users_by_id.get(user_id)

    def get_by_login(self, login: str) -> User | None:
        return self.users_by_login.get(login)

    def create(self, *, login: str, password_hash: str) -> User:
        user = User(
            id=uuid.uuid4(),
            login=login,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        self.users_by_id[user.id] = user
        self.users_by_login[login] = user
        return user


class FakeProjectRepo(ProjectRepositoryProtocol):
    def __init__(self) -> None:
        self.projects: dict[uuid.UUID, Project] = {}
        self.members: dict[tuple[uuid.UUID, uuid.UUID], ProjectRole] = {}

    def create_with_owner(self, *, owner_id: uuid.UUID, name: str, description: str) -> tuple[Project, ProjectRole]:
        now = datetime.now(UTC)
        project = Project(
            id=uuid.uuid4(),
            name=name,
            description=description,
            owner_id=owner_id,
            total_size_bytes=0,
            created_at=now,
            updated_at=now,
        )
        self.projects[project.id] = project
        self.members[(project.id, owner_id)] = ProjectRole.OWNER
        return project, ProjectRole.OWNER

    def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Project, ProjectRole]]:
        return [
            (self.projects[pid], role)
            for (pid, uid), role in self.members.items()
            if uid == user_id and pid in self.projects
        ]

    def get_for_user(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Project, ProjectRole] | None:
        role = self.members.get((project_id, user_id))
        project = self.projects.get(project_id)
        if role is None or project is None:
            return None
        return project, role

    def update(self, project: Project, *, name: str, description: str) -> Project:
        project.name = name
        project.description = description
        project.updated_at = datetime.now(UTC)
        return project

    def delete(self, project: Project) -> None:
        self.projects.pop(project.id, None)

    def is_member(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return (project_id, user_id) in self.members

    def add_member(self, *, project_id: uuid.UUID, user_id: uuid.UUID, role: ProjectRole) -> ProjectMember:
        self.members[(project_id, user_id)] = role
        return ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
        )


class FakeDocumentRepo(DocumentRepositoryProtocol):
    def __init__(self, project_repo: FakeProjectRepo) -> None:
        self._project_repo = project_repo
        self.docs: dict[uuid.UUID, Document] = {}

    def list_for_project(self, project_id: uuid.UUID) -> list[Document]:
        return [d for d in self.docs.values() if d.project_id == project_id]

    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self.docs.get(document_id)

    def get_by_project_and_filename(self, *, project_id: uuid.UUID, filename: str) -> Document | None:
        for doc in self.docs.values():
            if doc.project_id == project_id and doc.filename == filename:
                return doc
        return None

    def create(
        self,
        *,
        document_id: uuid.UUID,
        project_id: uuid.UUID,
        filename: str,
        content_type: str,
        s3_key: str,
        size_bytes: int,
        uploaded_by: uuid.UUID,
    ) -> Document:
        now = datetime.now(UTC)
        doc = Document(
            id=document_id,
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            s3_key=s3_key,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
            created_at=now,
            updated_at=now,
        )
        self.docs[doc.id] = doc
        self._recalc(project_id)
        return doc

    def update_file(
        self,
        document: Document,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        uploaded_by: uuid.UUID,
    ) -> Document:
        document.filename = filename
        document.content_type = content_type
        document.size_bytes = size_bytes
        document.uploaded_by = uploaded_by
        document.updated_at = datetime.now(UTC)
        self._recalc(document.project_id)
        return document

    def delete(self, document: Document) -> None:
        self.docs.pop(document.id, None)
        self._recalc(document.project_id)

    def _recalc(self, project_id: uuid.UUID) -> None:
        project = self._project_repo.projects.get(project_id)
        if project is not None:
            project.total_size_bytes = sum(d.size_bytes for d in self.list_for_project(project_id))


def _settings(max_file: int = 1024, max_project: int = 2048) -> Settings:
    return Settings(
        _env_file=None,
        storage_backend="memory",
        max_file_size_bytes=max_file,
        max_project_size_bytes=max_project,
    )


def test_project_service_permissions_and_cleanup_aaa() -> None:
    user_repo = FakeUserRepo()
    project_repo = FakeProjectRepo()
    doc_repo = FakeDocumentRepo(project_repo)
    storage = InMemoryStorageService()
    owner = user_repo.create(login="owner", password_hash="h")
    participant = user_repo.create(login="participant", password_hash="h")

    project_service = ProjectService(project_repo, user_repo, doc_repo, storage)
    doc_service = DocumentService(doc_repo, project_repo, storage, _settings())

    project, _ = project_service.create_project(owner_id=owner.id, name="P1", description="D1")
    project_service.invite_user(project_id=project.id, inviter_id=owner.id, target_login="participant")
    uploaded = doc_service.upload_documents(
        project_id=project.id,
        user_id=owner.id,
        files=[FileUploadPayload(filename="report.pdf", data=b"%PDF-1.4 content")],
    )
    s3_key = uploaded[0].s3_key

    # participant cannot delete project
    with pytest.raises(ForbiddenError):
        project_service.delete_project(project_id=project.id, user_id=participant.id)

    # Act: owner deletes project
    project_service.delete_project(project_id=project.id, user_id=owner.id)

    # Assert: S3 object was also cleaned up
    with pytest.raises(NotFoundError):
        storage.download(key=s3_key)


def test_document_service_validation_edge_cases_aaa() -> None:
    user_repo = FakeUserRepo()
    project_repo = FakeProjectRepo()
    doc_repo = FakeDocumentRepo(project_repo)
    storage = InMemoryStorageService()
    owner = user_repo.create(login="owner", password_hash="h")
    outsider = user_repo.create(login="outsider", password_hash="h")

    doc_service = DocumentService(doc_repo, project_repo, storage, _settings(max_file=100, max_project=150))
    project, _ = project_repo.create_with_owner(owner_id=owner.id, name="P1", description="")

    # empty upload batch
    with pytest.raises(BadRequestError):
        doc_service.upload_documents(project_id=project.id, user_id=owner.id, files=[])

    # empty filename
    with pytest.raises(BadRequestError):
        doc_service.upload_documents(
            project_id=project.id,
            user_id=owner.id,
            files=[FileUploadPayload(filename="   ", data=b"abc")],
        )

    # empty file content
    with pytest.raises(BadRequestError):
        doc_service.upload_documents(
            project_id=project.id,
            user_id=owner.id,
            files=[FileUploadPayload(filename="empty.pdf", data=b"")],
        )

    # duplicate filename in same batch
    with pytest.raises(BadRequestError):
        doc_service.upload_documents(
            project_id=project.id,
            user_id=owner.id,
            files=[
                FileUploadPayload(filename="same.pdf", data=b"123"),
                FileUploadPayload(filename="same.pdf", data=b"456"),
            ],
        )

    # project quota exceeded on upload
    with pytest.raises(PayloadTooLargeError):
        doc_service.upload_documents(
            project_id=project.id,
            user_id=owner.id,
            files=[
                FileUploadPayload(filename="a.pdf", data=b"x" * 90),
                FileUploadPayload(filename="b.pdf", data=b"y" * 90),
            ],
        )

    # Arrange two valid documents for update conflict & quota checks
    created = doc_service.upload_documents(
        project_id=project.id,
        user_id=owner.id,
        files=[
            FileUploadPayload(filename="first.pdf", data=b"x" * 60),
            FileUploadPayload(filename="second.pdf", data=b"y" * 60),
        ],
    )

    # renaming second.pdf to first.pdf causes 409 Conflict
    with pytest.raises(ConflictError):
        doc_service.update_document(
            document_id=created[1].id,
            user_id=owner.id,
            file=FileUploadPayload(filename="first.pdf", data=b"z" * 10),
        )

    # replacing second.pdf with 100 bytes exceeds 150-byte project quota (60 + 100 > 150)
    with pytest.raises(PayloadTooLargeError):
        doc_service.update_document(
            document_id=created[1].id,
            user_id=owner.id,
            file=FileUploadPayload(filename="second.pdf", data=b"z" * 100),
        )

    # outsider or missing document raises NotFoundError
    with pytest.raises(NotFoundError):
        doc_service.download_document(document_id=uuid.uuid4(), user_id=owner.id)

    with pytest.raises(NotFoundError):
        doc_service.download_document(document_id=created[0].id, user_id=outsider.id)
