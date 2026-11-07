from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_current_user, get_document_repository
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
from app.models import User
from app.repositories.document import DocumentRepository, FileUploadPayload

router = APIRouter(tags=["documents"])


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime


class DocumentDeletedResponse(BaseModel):
    id: int
    status: Literal["deleted"] = "deleted"


@router.get(
    "/project/{project_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
)
def list_project_documents(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> list[DocumentResponse]:
    try:
        docs = doc_repo.list_for_project(project_id=project_id, user_id=current_user.id)
        return [DocumentResponse.model_validate(doc) for doc in docs]
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from e
    except NoAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no access to the corresponding project",
        ) from e


@router.post(
    "/project/{project_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_documents(
    project_id: int,
    files: Annotated[list[UploadFile], File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> list[DocumentResponse]:
    payloads: list[FileUploadPayload] = []
    for upload in files:
        data = await upload.read()
        payloads.append(FileUploadPayload(filename=upload.filename or "", data=data))

    try:
        docs = doc_repo.upload_documents(
            project_id=project_id,
            user_id=current_user.id,
            files=payloads,
        )
        return [DocumentResponse.model_validate(doc) for doc in docs]
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from e
    except NoAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no access to the corresponding project",
        ) from e
    except (EmptyUploadError, DuplicateFilenameError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File type not supported",
        ) from e
    except DocumentAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with this filename already exists in the project",
        ) from e
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Storage quota exceeded",
        ) from e


@router.get("/document/{document_id}", status_code=status.HTTP_200_OK)
def download_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> Response:
    try:
        doc, content = doc_repo.download_document(document_id=document_id, user_id=current_user.id)
        encoded_name = quote(doc.filename)
        return Response(
            content=content,
            media_type=doc.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{encoded_name}"',
            },
        )
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from e
    except NoAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no access to the corresponding project",
        ) from e


@router.put("/document/{document_id}", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def update_document(
    document_id: int,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentResponse:
    data = await file.read()
    try:
        updated = doc_repo.update_document(
            document_id=document_id,
            user_id=current_user.id,
            file=FileUploadPayload(filename=file.filename or "", data=data),
        )
        return DocumentResponse.model_validate(updated)
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from e
    except NoAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no access to the corresponding project",
        ) from e
    except EmptyUploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File type not supported",
        ) from e
    except DocumentAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with this filename already exists in the project",
        ) from e
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Storage quota exceeded",
        ) from e


@router.delete("/document/{document_id}", response_model=DocumentDeletedResponse, status_code=status.HTTP_200_OK)
def delete_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentDeletedResponse:
    try:
        doc_repo.delete_document(document_id=document_id, user_id=current_user.id)
        return DocumentDeletedResponse(id=document_id, status="deleted")
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from e
    except NoAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no access to the corresponding project",
        ) from e
