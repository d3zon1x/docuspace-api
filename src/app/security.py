from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import PyJWTError
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import Settings
from app.errors import InvalidTokenError

_password_hasher = PasswordHash((BcryptHasher(),))


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _password_hasher.verify(plain_password, password_hash)


def create_access_token(user_id: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_expiry_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
        return int(payload["sub"])
    except (PyJWTError, ValueError, KeyError) as exc:
        raise InvalidTokenError("Invalid or expired access token") from exc
