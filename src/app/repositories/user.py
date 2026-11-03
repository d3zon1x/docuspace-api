import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepositoryProtocol(Protocol):
    def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_by_login(self, login: str) -> User | None: ...

    def create(self, *, login: str, password_hash: str) -> User: ...


class UserRepository(UserRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return self._session.scalar(stmt)

    def get_by_login(self, login: str) -> User | None:
        stmt = select(User).where(User.login == login)
        return self._session.scalar(stmt)

    def create(self, *, login: str, password_hash: str) -> User:
        user = User(login=login, password_hash=password_hash)
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user
