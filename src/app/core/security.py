import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import Settings
from app.core.errors import UnauthorizedError

_password_hasher = PasswordHash((BcryptHasher(),))


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _password_hasher.verify(plain_password, password_hash)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_expiry_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
    except InvalidTokenError as exc:
        raise UnauthorizedError(
            "Invalid or expired access token.",
            code="INVALID_TOKEN",
        ) from exc

    try:
        return uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise UnauthorizedError(
            "Invalid token subject.",
            code="INVALID_TOKEN",
        ) from exc
