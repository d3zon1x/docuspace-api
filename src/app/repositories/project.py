from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import (
    AlreadyProjectMemberError,
    NoAccessError,
    OwnerRequiredError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from app.models import Document, Project, ProjectMember, ProjectRole, User
from app.repositories.storage import StorageBackend


class ProjectRepository:
    def __init__(self, session: Session, storage: StorageBackend | None = None) -> None:
        self._session = session
        self._storage = storage

    def create(self, *, owner_id: int, name: str, description: str) -> tuple[Project, ProjectRole]:
        project = Project(name=name, description=description, owner_id=owner_id, total_size_bytes=0)
        self._session.add(project)
        self._session.flush()

        membership = ProjectMember(project_id=project.id, user_id=owner_id, role=ProjectRole.OWNER)
        self._session.add(membership)
        self._session.commit()
        self._session.refresh(project)
        return project, ProjectRole.OWNER

    def list_for_user(self, user_id: int) -> list[tuple[Project, ProjectRole]]:
        stmt = (
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        rows = self._session.execute(stmt).all()
        return [(row[0], row[1]) for row in rows]

    def get_for_user(self, *, project_id: int, user_id: int) -> tuple[Project, ProjectRole]:
        project = self._session.get(Project, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")

        membership = self._session.get(ProjectMember, (project_id, user_id))
        if membership is None:
            raise NoAccessError("User does not have access to this project")

        return project, membership.role

    def update(self, *, project_id: int, user_id: int, name: str, description: str) -> tuple[Project, ProjectRole]:
        project, role = self.get_for_user(project_id=project_id, user_id=user_id)
        project.name = name
        project.description = description
        self._session.commit()
        self._session.refresh(project)
        return project, role

    def delete(self, *, project_id: int, user_id: int) -> None:
        project, role = self.get_for_user(project_id=project_id, user_id=user_id)
        if role != ProjectRole.OWNER:
            raise OwnerRequiredError("Only the project owner can delete the project")

        if self._storage is not None:
            docs_stmt = select(Document).where(Document.project_id == project.id)
            for doc in self._session.scalars(docs_stmt).all():
                self._storage.delete(key=doc.s3_key)

        self._session.delete(project)
        self._session.commit()

    def invite_user(self, *, project_id: int, inviter_id: int, target_login: str) -> ProjectRole:
        project, role = self.get_for_user(project_id=project_id, user_id=inviter_id)
        if role != ProjectRole.OWNER:
            raise OwnerRequiredError("Only the project owner can invite users")

        target_user = self._session.scalar(select(User).where(User.login == target_login))
        if target_user is None:
            raise UserNotFoundError(f"User '{target_login}' not found")

        existing = self._session.get(ProjectMember, (project.id, target_user.id))
        if existing is not None:
            raise AlreadyProjectMemberError("User is already a member of the project")

        membership = ProjectMember(
            project_id=project.id,
            user_id=target_user.id,
            role=ProjectRole.PARTICIPANT,
        )
        self._session.add(membership)
        self._session.commit()
        return membership.role
