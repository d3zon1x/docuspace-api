import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, get_project_service
from app.models.project import Project, ProjectRole
from app.models.user import User
from app.services.project import ProjectService

router = APIRouter(tags=["projects"])


class ProjectUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    role: ProjectRole
    total_size_bytes: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, project: Project, role: ProjectRole) -> "ProjectResponse":
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            role=role,
            total_size_bytes=project.total_size_bytes,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class ProjectDeletedResponse(BaseModel):
    id: uuid.UUID
    status: Literal["deleted"] = "deleted"


class ProjectInviteResponse(BaseModel):
    project_id: uuid.UUID
    invited_user: str
    role: ProjectRole


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectUpsertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    project, role = project_service.create_project(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )
    return ProjectResponse.from_model(project, role)


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    status_code=status.HTTP_200_OK,
)
def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ProjectResponse]:
    items = project_service.list_projects(user_id=current_user.id)
    return [ProjectResponse.from_model(project, role) for project, role in items]


@router.get(
    "/project/{project_id}/info",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_info(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    project, role = project_service.get_project_info(project_id=project_id, user_id=current_user.id)
    return ProjectResponse.from_model(project, role)


@router.put(
    "/project/{project_id}/info",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
)
def update_project_info(
    project_id: uuid.UUID,
    payload: ProjectUpsertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    project, role = project_service.update_project_info(
        project_id=project_id,
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )
    return ProjectResponse.from_model(project, role)


@router.delete(
    "/project/{project_id}",
    response_model=ProjectDeletedResponse,
    status_code=status.HTTP_200_OK,
)
def delete_project(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectDeletedResponse:
    project_service.delete_project(project_id=project_id, user_id=current_user.id)
    return ProjectDeletedResponse(id=project_id, status="deleted")


@router.post(
    "/project/{project_id}/invite",
    response_model=ProjectInviteResponse,
    status_code=status.HTTP_200_OK,
)
def invite_user_to_project(
    project_id: uuid.UUID,
    user: Annotated[str, Query(min_length=1, max_length=64)],
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectInviteResponse:
    role = project_service.invite_user(
        project_id=project_id,
        inviter_id=current_user.id,
        target_login=user,
    )
    return ProjectInviteResponse(project_id=project_id, invited_user=user, role=role)
