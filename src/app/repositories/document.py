import os
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DuplicateFilenameError,
    EmptyUploadError,
    NoAccessError,
    ProjectNotFoundError,
    QuotaExceededError,
    UnsupportedFileTypeError,
)
from app.models import Document, Project, ProjectMember
from app.repositories.storage import StorageBackend

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(slots=True)
class FileUploadPayload:
    filename: str
    data: bytes


class DocumentRepository:
    def __init__(self, session: Session, storage: StorageBackend, settings: Settings) -> None:
        self._session = session
        self._storage = storage
        self._settings = settings

    def list_for_project(self, *, project_id: int, user_id: int) -> list[Document]:
        self._require_project_access(project_id=project_id, user_id=user_id)
        stmt = select(Document).where(Document.project_id == project_id).order_by(Document.created_at.desc())
        return list(self._session.scalars(stmt).all())

    def upload_documents(self, *, project_id: int, user_id: int, files: list[FileUploadPayload]) -> list[Document]:
        project = self._require_project_access(project_id=project_id, user_id=user_id)
        if not files:
            raise EmptyUploadError("At least one document file must be provided")

        seen_names: set[str] = set()
        validated: list[tuple[str, str, bytes]] = []
        batch_size = 0

        for item in files:
            clean_name, content_type = self._validate_file(item.filename, item.data)
            if clean_name in seen_names:
                raise DuplicateFilenameError(f"Duplicate filename '{clean_name}' in upload request")
            seen_names.add(clean_name)

            if self._get_by_project_and_filename(project_id=project_id, filename=clean_name) is not None:
                raise DocumentAlreadyExistsError(f"Document '{clean_name}' already exists in this project")

            batch_size += len(item.data)
            validated.append((clean_name, content_type, item.data))

        if project.total_size_bytes + batch_size > self._settings.max_project_size_bytes:
            raise QuotaExceededError("Total project storage quota exceeded")

        created_docs: list[Document] = []
        for clean_name, content_type, data in validated:
            doc = Document(
                project_id=project_id,
                filename=clean_name,
                content_type=content_type,
                s3_key="",
                size_bytes=len(data),
                uploaded_by=user_id,
            )
            self._session.add(doc)
            self._session.flush()
            doc.s3_key = f"projects/{project_id}/{doc.id}"
            self._storage.upload(key=doc.s3_key, data=data, content_type=content_type)
            created_docs.append(doc)

        self._recalculate_project_size(project_id)
        self._session.commit()
        for doc in created_docs:
            self._session.refresh(doc)
        return created_docs

    def download_document(self, *, document_id: int, user_id: int) -> tuple[Document, bytes]:
        document = self._require_document_access(document_id=document_id, user_id=user_id)
        content = self._storage.download(key=document.s3_key)
        return document, content

    def update_document(self, *, document_id: int, user_id: int, file: FileUploadPayload) -> Document:
        document = self._require_document_access(document_id=document_id, user_id=user_id)
        project = self._require_project_access(project_id=document.project_id, user_id=user_id)

        clean_name, content_type = self._validate_file(file.filename, file.data)

        existing = self._get_by_project_and_filename(project_id=document.project_id, filename=clean_name)
        if existing is not None and existing.id != document.id:
            raise DocumentAlreadyExistsError(f"Document '{clean_name}' already exists in this project")

        projected_total = project.total_size_bytes - document.size_bytes + len(file.data)
        if projected_total > self._settings.max_project_size_bytes:
            raise QuotaExceededError("Total project storage quota exceeded")

        self._storage.upload(key=document.s3_key, data=file.data, content_type=content_type)
        document.filename = clean_name
        document.content_type = content_type
        document.size_bytes = len(file.data)
        document.uploaded_by = user_id
        self._session.flush()
        self._recalculate_project_size(document.project_id)
        self._session.commit()
        self._session.refresh(document)
        return document

    def delete_document(self, *, document_id: int, user_id: int) -> None:
        document = self._require_document_access(document_id=document_id, user_id=user_id)
        project_id = document.project_id
        self._storage.delete(key=document.s3_key)
        self._session.delete(document)
        self._session.flush()
        self._recalculate_project_size(project_id)
        self._session.commit()

    def _get_by_project_and_filename(self, *, project_id: int, filename: str) -> Document | None:
        stmt = select(Document).where(Document.project_id == project_id, Document.filename == filename)
        return self._session.scalar(stmt)

    def _require_project_access(self, *, project_id: int, user_id: int) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        membership = self._session.get(ProjectMember, (project_id, user_id))
        if membership is None:
            raise NoAccessError("User does not have access to this project")
        return project

    def _require_document_access(self, *, document_id: int, user_id: int) -> Document:
        document = self._session.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        membership = self._session.get(ProjectMember, (document.project_id, user_id))
        if membership is None:
            raise NoAccessError("User does not have access to the corresponding project")
        return document

    def _recalculate_project_size(self, project_id: int) -> None:
        total_stmt = select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.project_id == project_id)
        total_bytes = int(self._session.scalar(total_stmt) or 0)
        project = self._session.get(Project, project_id)
        if project is not None:
            project.total_size_bytes = total_bytes

    def _validate_file(self, filename: str, data: bytes) -> tuple[str, str]:
        clean_name = os.path.basename(filename.strip())
        if not clean_name:
            raise EmptyUploadError("Document filename cannot be empty")

        _, ext = os.path.splitext(clean_name.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError("Only .pdf and .docx documents are supported")

        if len(data) == 0:
            raise EmptyUploadError("Uploaded document cannot be empty")

        if len(data) > self._settings.max_file_size_bytes:
            raise QuotaExceededError(
                f"File '{clean_name}' exceeds maximum allowed size of {self._settings.max_file_size_bytes} bytes"
            )

        return clean_name, ALLOWED_EXTENSIONS[ext]
