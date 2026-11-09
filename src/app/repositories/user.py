from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import (
    InvalidCredentialsError,
    PasswordsDoNotMatchError,
    UserAlreadyExistsError,
)
from app.models import User
from app.security import create_access_token, hash_password, verify_password


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_login(self, login: str) -> User | None:
        stmt = select(User).where(User.login == login)
        return self._session.scalar(stmt)

    def register(self, *, login: str, password: str, repeat_password: str) -> User:
        if password != repeat_password:
            raise PasswordsDoNotMatchError("Passwords do not match")

        if self.get_by_login(login) is not None:
            raise UserAlreadyExistsError("User with this login already exists")

        user = User(login=login, password_hash=hash_password(password))
        self._session.add(user)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise UserAlreadyExistsError("User with this login already exists") from exc

        self._session.refresh(user)
        return user

    def authenticate(self, *, login: str, password: str, settings: Settings) -> tuple[str, int]:
        user = self.get_by_login(login)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid login or password")

        token = create_access_token(user.id, settings)
        return token, settings.jwt_expiry_seconds
