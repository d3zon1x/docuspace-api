from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepositoryProtocol


class AuthService:
    def __init__(self, user_repository: UserRepositoryProtocol, settings: Settings) -> None:
        self._users = user_repository
        self._settings = settings

    def register(self, *, login: str, password: str, repeat_password: str) -> User:
        if password != repeat_password:
            raise BadRequestError(
                "Passwords do not match.",
                code="PASSWORDS_DO_NOT_MATCH",
            )

        if self._users.get_by_login(login) is not None:
            raise ConflictError(
                "User with this login already exists.",
                code="USER_ALREADY_EXISTS",
            )

        password_hash = hash_password(password)
        try:
            return self._users.create(login=login, password_hash=password_hash)
        except IntegrityError as exc:
            raise ConflictError(
                "User with this login already exists.",
                code="USER_ALREADY_EXISTS",
            ) from exc

    def login(self, *, login: str, password: str) -> tuple[str, int]:
        user = self._users.get_by_login(login)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError(
                "Invalid login or password.",
                code="INVALID_CREDENTIALS",
            )

        token = create_access_token(user.id, self._settings)
        return token, self._settings.jwt_expiry_seconds
