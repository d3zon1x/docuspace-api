from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, get_project_repository
from app.errors import (
    AlreadyProjectMemberError,
    NoAccessError,
    OwnerRequiredError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from app.models import Project, ProjectRole, User
from app.repositories.project import ProjectRepository

router = APIRouter(tags=["projects"])


class ProjectUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class ProjectResponse(BaseModel):
    id: int
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
    id: int
    status: Literal["deleted"] = "deleted"


class ProjectInviteResponse(BaseModel):
    project_id: int
    invited_user: str
    role: ProjectRole


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectUpsertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> ProjectResponse:
    project, role = project_repo.create(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )
    return ProjectResponse.from_model(project, role)


@router.get("/projects", response_model=list[ProjectResponse], status_code=status.HTTP_200_OK)
def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> list[ProjectResponse]:
    items = project_repo.list_for_user(current_user.id)
    return [ProjectResponse.from_model(project, role) for project, role in items]


@router.get("/project/{project_id}/info", response_model=ProjectResponse, status_code=status.HTTP_200_OK)
def get_project_info(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> ProjectResponse:
    try:
        project, role = project_repo.get_for_user(project_id=project_id, user_id=current_user.id)
        return ProjectResponse.from_model(project, role)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from e
    except NoAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no access to this project",
        ) from e


@router.put("/project/{project_id}/info", response_model=ProjectResponse, status_code=status.HTTP_200_OK)
def update_project_info(
    project_id: int,
    payload: ProjectUpsertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> ProjectResponse:
    try:
        project, role = project_repo.update(
            project_id=project_id,
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
        )
        return ProjectResponse.from_model(project, role)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from e
    except NoAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no access to this project",
        ) from e


@router.delete("/project/{project_id}", response_model=ProjectDeletedResponse, status_code=status.HTTP_200_OK)
def delete_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> ProjectDeletedResponse:
    try:
        project_repo.delete(project_id=project_id, user_id=current_user.id)
        return ProjectDeletedResponse(id=project_id, status="deleted")
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from e
    except (NoAccessError, OwnerRequiredError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can delete the project",
        ) from e


@router.post("/project/{project_id}/invite", response_model=ProjectInviteResponse, status_code=status.HTTP_200_OK)
def invite_user_to_project(
    project_id: int,
    user: Annotated[str, Query(min_length=1, max_length=64)],
    current_user: Annotated[User, Depends(get_current_user)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> ProjectInviteResponse:
    try:
        role = project_repo.invite_user(
            project_id=project_id,
            inviter_id=current_user.id,
            target_login=user,
        )
        return ProjectInviteResponse(project_id=project_id, invited_user=user, role=role)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from e
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found",
        ) from e
    except (NoAccessError, OwnerRequiredError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can invite users",
        ) from e
    except AlreadyProjectMemberError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of the project",
        ) from e
