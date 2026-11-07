import jwt
import pytest

from app.config import Settings
from app.errors import InvalidTokenError
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        jwt_secret="test-secret-key-at-least-32-characters-long",
        jwt_expiry_seconds=3600,
    )


def test_password_hash_and_verify() -> None:
    digest = hash_password("StrongPass123!")

    assert digest != "StrongPass123!"
    assert verify_password("StrongPass123!", digest) is True
    assert verify_password("WrongPassword!", digest) is False


def test_access_token_round_trip() -> None:
    settings = _test_settings()

    token = create_access_token(42, settings)
    decoded_id = decode_access_token(token, settings)

    assert decoded_id == 42


def test_decode_access_token_rejects_invalid_token() -> None:
    settings = _test_settings()

    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt", settings)

    bad_sub_token = jwt.encode(
        {"sub": "not-an-int", "iat": 1, "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(bad_sub_token, settings)
