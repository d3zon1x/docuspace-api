from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_app_settings, get_user_repository
from app.config import Settings
from app.errors import (
    InvalidCredentialsError,
    PasswordsDoNotMatchError,
    UserAlreadyExistsError,
)
from app.repositories.user import UserRepository

router = APIRouter(tags=["auth"])


class RegisterRequest(BaseModel):
    login: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    repeat_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    created_at: datetime


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


@router.post("/auth", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: RegisterRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserResponse:
    try:
        user = user_repo.register(
            login=payload.login,
            password=payload.password,
            repeat_password=payload.repeat_password,
        )
        return UserResponse.model_validate(user)
    except PasswordsDoNotMatchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        ) from e
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this login already exists",
        ) from e


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login_user(
    payload: LoginRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> TokenResponse:
    try:
        access_token, expires_in = user_repo.authenticate(
            login=payload.login,
            password=payload.password,
            settings=settings,
        )
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login or password",
        ) from e
