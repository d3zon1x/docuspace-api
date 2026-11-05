import os
import uuid
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError, PayloadTooLargeError
from app.models.document import Document
from app.models.project import Project
from app.repositories.document import DocumentRepositoryProtocol
from app.repositories.project import ProjectRepositoryProtocol
from app.services.storage import StorageServiceProtocol

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(slots=True)
class FileUploadPayload:
    filename: str
    data: bytes


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepositoryProtocol,
        project_repository: ProjectRepositoryProtocol,
        storage_service: StorageServiceProtocol,
        settings: Settings,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._storage = storage_service
        self._settings = settings

    def list_project_documents(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> list[Document]:
        self._require_project_access(project_id=project_id, user_id=user_id)
        return self._documents.list_for_project(project_id)

    def upload_documents(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        files: list[FileUploadPayload],
    ) -> list[Document]:
        project = self._require_project_access(project_id=project_id, user_id=user_id)
        if not files:
            raise BadRequestError(
                "At least one document file must be provided.",
                code="EMPTY_UPLOAD",
            )

        seen_names: set[str] = set()
        validated: list[tuple[str, str, bytes]] = []
        batch_size = 0

        for item in files:
            clean_name, content_type = self._validate_file(item.filename, item.data)
            if clean_name in seen_names:
                raise BadRequestError(
                    f"Duplicate filename '{clean_name}' in the same upload request.",
                    code="DUPLICATE_FILENAME_IN_BATCH",
                )
            seen_names.add(clean_name)

            if self._documents.get_by_project_and_filename(project_id=project_id, filename=clean_name) is not None:
                raise ConflictError(
                    f"Document '{clean_name}' already exists in this project.",
                    code="DOCUMENT_ALREADY_EXISTS",
                )

            batch_size += len(item.data)
            validated.append((clean_name, content_type, item.data))

        if project.total_size_bytes + batch_size > self._settings.max_project_size_bytes:
            raise PayloadTooLargeError(
                "Total project storage quota exceeded.",
                code="PROJECT_QUOTA_EXCEEDED",
            )

        created_docs: list[Document] = []
        for clean_name, content_type, data in validated:
            doc_id = uuid.uuid4()
            s3_key = f"projects/{project_id}/{doc_id}"
            self._storage.upload(key=s3_key, data=data, content_type=content_type)
            doc = self._documents.create(
                document_id=doc_id,
                project_id=project_id,
                filename=clean_name,
                content_type=content_type,
                s3_key=s3_key,
                size_bytes=len(data),
                uploaded_by=user_id,
            )
            created_docs.append(doc)

        return created_docs

    def download_document(self, *, document_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Document, bytes]:
        document = self._require_document_access(document_id=document_id, user_id=user_id)
        content = self._storage.download(key=document.s3_key)
        return document, content

    def update_document(
        self,
        *,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        file: FileUploadPayload,
    ) -> Document:
        document = self._require_document_access(document_id=document_id, user_id=user_id)
        project = self._require_project_access(project_id=document.project_id, user_id=user_id)

        clean_name, content_type = self._validate_file(file.filename, file.data)

        existing = self._documents.get_by_project_and_filename(
            project_id=document.project_id,
            filename=clean_name,
        )
        if existing is not None and existing.id != document.id:
            raise ConflictError(
                f"Document '{clean_name}' already exists in this project.",
                code="DOCUMENT_ALREADY_EXISTS",
            )

        projected_total = project.total_size_bytes - document.size_bytes + len(file.data)
        if projected_total > self._settings.max_project_size_bytes:
            raise PayloadTooLargeError(
                "Total project storage quota exceeded.",
                code="PROJECT_QUOTA_EXCEEDED",
            )

        self._storage.upload(key=document.s3_key, data=file.data, content_type=content_type)
        return self._documents.update_file(
            document,
            filename=clean_name,
            content_type=content_type,
            size_bytes=len(file.data),
            uploaded_by=user_id,
        )

    def delete_document(self, *, document_id: uuid.UUID, user_id: uuid.UUID) -> None:
        document = self._require_document_access(document_id=document_id, user_id=user_id)
        self._storage.delete(key=document.s3_key)
        self._documents.delete(document)

    def _require_project_access(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
        result = self._projects.get_for_user(project_id=project_id, user_id=user_id)
        if result is None:
            raise NotFoundError(
                "Project not found or user does not have access.",
                code="PROJECT_NOT_FOUND",
            )
        return result[0]

    def _require_document_access(self, *, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
        document = self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(
                "Document not found or user does not have access.",
                code="DOCUMENT_NOT_FOUND",
            )
        if self._projects.get_for_user(project_id=document.project_id, user_id=user_id) is None:
            raise NotFoundError(
                "Document not found or user does not have access.",
                code="DOCUMENT_NOT_FOUND",
            )
        return document

    def _validate_file(self, filename: str, data: bytes) -> tuple[str, str]:
        clean_name = os.path.basename(filename.strip())
        if not clean_name:
            raise BadRequestError(
                "Document filename cannot be empty.",
                code="INVALID_FILENAME",
            )

        _, ext = os.path.splitext(clean_name.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise BadRequestError(
                "Only .pdf and .docx documents are supported.",
                code="UNSUPPORTED_FILE_TYPE",
            )

        if len(data) == 0:
            raise BadRequestError(
                "Uploaded document cannot be empty.",
                code="EMPTY_FILE",
            )

        if len(data) > self._settings.max_file_size_bytes:
            raise PayloadTooLargeError(
                f"File '{clean_name}' exceeds maximum allowed size of {self._settings.max_file_size_bytes} bytes.",
                code="FILE_TOO_LARGE",
            )

        return clean_name, ALLOWED_EXTENSIONS[ext]
