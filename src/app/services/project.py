import uuid

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.project import Project, ProjectRole
from app.repositories.project import ProjectRepositoryProtocol
from app.repositories.user import UserRepositoryProtocol


class ProjectService:
    def __init__(self, project_repository: ProjectRepositoryProtocol, user_repository: UserRepositoryProtocol) -> None:
        self._projects = project_repository
        self._users = user_repository

    def create_project(self, *, owner_id: uuid.UUID, name: str, description: str) -> tuple[Project, ProjectRole]:
        return self._projects.create_with_owner(owner_id=owner_id, name=name, description=description)

    def list_projects(self, *, user_id: uuid.UUID) -> list[tuple[Project, ProjectRole]]:
        return self._projects.list_for_user(user_id)

    def get_project_info(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Project, ProjectRole]:
        result = self._projects.get_for_user(project_id=project_id, user_id=user_id)
        if result is None:
            raise NotFoundError(
                "Project not found or user does not have access.",
                code="PROJECT_NOT_FOUND",
            )
        return result

    def update_project_info(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        description: str,
    ) -> tuple[Project, ProjectRole]:
        project, role = self.get_project_info(project_id=project_id, user_id=user_id)
        updated = self._projects.update(project, name=name, description=description)
        return updated, role

    def delete_project(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        project, role = self.get_project_info(project_id=project_id, user_id=user_id)
        if role != ProjectRole.OWNER:
            raise ForbiddenError(
                "Only the project owner can delete the project.",
                code="OWNER_REQUIRED",
            )
        self._projects.delete(project)

    def invite_user(self, *, project_id: uuid.UUID, inviter_id: uuid.UUID, target_login: str) -> ProjectRole:
        project, role = self.get_project_info(project_id=project_id, user_id=inviter_id)
        if role != ProjectRole.OWNER:
            raise ForbiddenError(
                "Only the project owner can invite users.",
                code="OWNER_REQUIRED",
            )

        target_user = self._users.get_by_login(target_login)
        if target_user is None:
            raise NotFoundError(
                f"User '{target_login}' not found.",
                code="USER_NOT_FOUND",
            )

        if self._projects.is_member(project_id=project.id, user_id=target_user.id):
            raise ConflictError(
                "User is already a member of the project.",
                code="ALREADY_PROJECT_MEMBER",
            )

        membership = self._projects.add_member(
            project_id=project.id,
            user_id=target_user.id,
            role=ProjectRole.PARTICIPANT,
        )
        return membership.role
