import uuid
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.project import Project


class DocumentRepositoryProtocol(Protocol):
    def list_for_project(self, project_id: uuid.UUID) -> list[Document]: ...

    def get_by_id(self, document_id: uuid.UUID) -> Document | None: ...

    def get_by_project_and_filename(self, *, project_id: uuid.UUID, filename: str) -> Document | None: ...

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
    ) -> Document: ...

    def update_file(
        self,
        document: Document,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        uploaded_by: uuid.UUID,
    ) -> Document: ...

    def delete(self, document: Document) -> None: ...


class DocumentRepository(DocumentRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_project(self, project_id: uuid.UUID) -> list[Document]:
        stmt = select(Document).where(Document.project_id == project_id).order_by(Document.created_at.desc())
        return list(self._session.scalars(stmt).all())

    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        stmt = select(Document).where(Document.id == document_id)
        return self._session.scalar(stmt)

    def get_by_project_and_filename(self, *, project_id: uuid.UUID, filename: str) -> Document | None:
        stmt = select(Document).where(Document.project_id == project_id, Document.filename == filename)
        return self._session.scalar(stmt)

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
        document = Document(
            id=document_id,
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            s3_key=s3_key,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
        )
        self._session.add(document)
        self._session.flush()
        self._recalculate_project_size(project_id)
        self._session.commit()
        self._session.refresh(document)
        return document

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
        self._session.flush()
        self._recalculate_project_size(document.project_id)
        self._session.commit()
        self._session.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        project_id = document.project_id
        self._session.delete(document)
        self._session.flush()
        self._recalculate_project_size(project_id)
        self._session.commit()

    def _recalculate_project_size(self, project_id: uuid.UUID) -> None:
        total_stmt = select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.project_id == project_id)
        total_bytes = int(self._session.scalar(total_stmt) or 0)
        project = self._session.get(Project, project_id)
        if project is not None:
            project.total_size_bytes = total_bytes
