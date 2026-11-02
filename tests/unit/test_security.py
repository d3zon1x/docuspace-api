import uuid

import pytest

from app.core.config import Settings
from app.core.errors import BadRequestError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_email_verification_token,
    decode_access_token,
    decode_email_verification_token,
    hash_password,
    verify_password,
)
from app.services.email import EmailService


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        jwt_secret="test-secret-key-at-least-32-characters-long",
        jwt_expiry_seconds=3600,
        email_token_expiry_seconds=86400,
        public_base_url="http://localhost:8000",
        smtp_enabled=False,
    )


def test_password_hash_and_verify() -> None:
    """Hashed passwords verify against the original plain password and reject wrong ones."""
    digest = hash_password("StrongPass123!")

    assert digest != "StrongPass123!"
    assert verify_password("StrongPass123!", digest) is True
    assert verify_password("WrongPassword!", digest) is False


def test_access_token_round_trip() -> None:
    """Access JWT encodes and decodes the user UUID."""
    settings = _test_settings()
    user_id = uuid.uuid4()

    token = create_access_token(user_id, settings)
    decoded_id = decode_access_token(token, settings)

    assert decoded_id == user_id


def test_decode_access_token_rejects_invalid_or_wrong_purpose_token() -> None:
    """Invalid tokens or email verification tokens cannot be used as access tokens."""
    settings = _test_settings()
    user_id = uuid.uuid4()

    with pytest.raises(UnauthorizedError):
        decode_access_token("not-a-jwt", settings)

    email_token = create_email_verification_token(user_id, "alex@example.com", settings)
    with pytest.raises(UnauthorizedError):
        decode_access_token(email_token, settings)


def test_email_verification_token_round_trip() -> None:
    """Email verification token encodes and decodes `(user_id, email)`."""
    settings = _test_settings()
    user_id = uuid.uuid4()

    token = create_email_verification_token(user_id, "alex@example.com", settings)
    decoded_id, decoded_email = decode_email_verification_token(token, settings)

    assert decoded_id == user_id
    assert decoded_email == "alex@example.com"


def test_decode_email_verification_token_rejects_access_token() -> None:
    """Access token cannot be used as an email verification token."""
    settings = _test_settings()
    access_token = create_access_token(uuid.uuid4(), settings)

    with pytest.raises(BadRequestError):
        decode_email_verification_token(access_token, settings)

    with pytest.raises(BadRequestError):
        decode_email_verification_token("malformed-token", settings)


def test_email_service_builds_verification_url_when_smtp_disabled() -> None:
    """EmailService constructs the verification URL and logs when SMTP is disabled."""
    settings = _test_settings()
    service = EmailService(settings)

    url = service.send_verification_email(
        recipient_email="alex@example.com",
        login="alex_dev",
        token="sample-token",
    )

    assert url == "http://localhost:8000/auth/verify?token=sample-token"
