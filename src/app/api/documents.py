import uuid
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_current_user, get_document_service
from app.models.user import User
from app.services.document import DocumentService, FileUploadPayload

router = APIRouter(tags=["documents"])


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime


class DocumentDeletedResponse(BaseModel):
    id: uuid.UUID
    status: Literal["deleted"] = "deleted"


@router.get(
    "/project/{project_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
)
def list_project_documents(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentResponse]:
    docs = document_service.list_project_documents(project_id=project_id, user_id=current_user.id)
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.post(
    "/project/{project_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_documents(
    project_id: uuid.UUID,
    files: Annotated[list[UploadFile], File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentResponse]:
    payloads: list[FileUploadPayload] = []
    for upload in files:
        data = await upload.read()
        payloads.append(FileUploadPayload(filename=upload.filename or "", data=data))

    docs = document_service.upload_documents(
        project_id=project_id,
        user_id=current_user.id,
        files=payloads,
    )
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get(
    "/document/{document_id}",
    status_code=status.HTTP_200_OK,
)
def download_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> Response:
    doc, content = document_service.download_document(document_id=document_id, user_id=current_user.id)
    encoded_name = quote(doc.filename)
    return Response(
        content=content,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{encoded_name}"',
        },
    )


@router.put(
    "/document/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def update_document(
    document_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    data = await file.read()
    updated = document_service.update_document(
        document_id=document_id,
        user_id=current_user.id,
        file=FileUploadPayload(filename=file.filename or "", data=data),
    )
    return DocumentResponse.model_validate(updated)


@router.delete(
    "/document/{document_id}",
    response_model=DocumentDeletedResponse,
    status_code=status.HTTP_200_OK,
)
def delete_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentDeletedResponse:
    document_service.delete_document(document_id=document_id, user_id=current_user.id)
    return DocumentDeletedResponse(id=document_id, status="deleted")
