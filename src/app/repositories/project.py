import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember, ProjectRole


class ProjectRepositoryProtocol(Protocol):
    def create_with_owner(self, *, owner_id: uuid.UUID, name: str, description: str) -> tuple[Project, ProjectRole]: ...

    def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Project, ProjectRole]]: ...

    def get_for_user(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Project, ProjectRole] | None: ...

    def update(self, project: Project, *, name: str, description: str) -> Project: ...

    def delete(self, project: Project) -> None: ...

    def is_member(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    def add_member(self, *, project_id: uuid.UUID, user_id: uuid.UUID, role: ProjectRole) -> ProjectMember: ...


class ProjectRepository(ProjectRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_with_owner(self, *, owner_id: uuid.UUID, name: str, description: str) -> tuple[Project, ProjectRole]:
        project = Project(name=name, description=description, owner_id=owner_id, total_size_bytes=0)
        self._session.add(project)
        self._session.flush()

        membership = ProjectMember(project_id=project.id, user_id=owner_id, role=ProjectRole.OWNER)
        self._session.add(membership)
        self._session.commit()
        self._session.refresh(project)
        return project, ProjectRole.OWNER

    def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Project, ProjectRole]]:
        stmt = (
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        rows = self._session.execute(stmt).all()
        return [(row[0], row[1]) for row in rows]

    def get_for_user(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Project, ProjectRole] | None:
        stmt = (
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(Project.id == project_id, ProjectMember.user_id == user_id)
        )
        row = self._session.execute(stmt).first()
        if row is None:
            return None
        return row[0], row[1]

    def update(self, project: Project, *, name: str, description: str) -> Project:
        project.name = name
        project.description = description
        self._session.commit()
        self._session.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self._session.delete(project)
        self._session.commit()

    def is_member(self, *, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        return self._session.scalar(stmt) is not None

    def add_member(self, *, project_id: uuid.UUID, user_id: uuid.UUID, role: ProjectRole) -> ProjectMember:
        membership = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        self._session.add(membership)
        self._session.commit()
        return membership
