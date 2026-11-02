import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import Settings
from app.core.errors import BadRequestError, UnauthorizedError

_password_hasher = PasswordHash((BcryptHasher(),))

ACCESS_TOKEN_PURPOSE = "access"
EMAIL_VERIFY_PURPOSE = "email_verify"
PROJECT_INVITE_PURPOSE = "project_invite"


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _password_hasher.verify(plain_password, password_hash)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "purpose": ACCESS_TOKEN_PURPOSE,
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
            options={"require": ["sub", "purpose", "iat", "exp"]},
        )
    except InvalidTokenError as exc:
        raise UnauthorizedError(
            "Invalid or expired access token.",
            code="INVALID_TOKEN",
        ) from exc

    if payload.get("purpose") != ACCESS_TOKEN_PURPOSE:
        raise UnauthorizedError(
            "Invalid token purpose.",
            code="INVALID_TOKEN",
        )

    try:
        return uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise UnauthorizedError(
            "Invalid token subject.",
            code="INVALID_TOKEN",
        ) from exc


def create_email_verification_token(user_id: uuid.UUID, email: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "purpose": EMAIL_VERIFY_PURPOSE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.email_token_expiry_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_email_verification_token(token: str, settings: Settings) -> tuple[uuid.UUID, str]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "email", "purpose", "iat", "exp"]},
        )
    except InvalidTokenError as exc:
        raise BadRequestError(
            "Invalid or expired verification token.",
            code="INVALID_VERIFICATION_TOKEN",
        ) from exc

    if payload.get("purpose") != EMAIL_VERIFY_PURPOSE:
        raise BadRequestError(
            "Invalid verification token purpose.",
            code="INVALID_VERIFICATION_TOKEN",
        )

    try:
        return uuid.UUID(str(payload["sub"])), str(payload["email"])
    except (ValueError, KeyError) as exc:
        raise BadRequestError(
            "Invalid verification token payload.",
            code="INVALID_VERIFICATION_TOKEN",
        ) from exc
