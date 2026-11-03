import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_auth_service
from app.services.auth import AuthService

router = APIRouter(tags=["auth"])


class RegisterRequest(BaseModel):
    login: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    repeat_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
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
    payload: RegisterRequest, auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> UserResponse:
    user = auth_service.register(
        login=payload.login,
        password=payload.password,
        repeat_password=payload.repeat_password,
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login_user(
    payload: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    access_token, expires_in = auth_service.login(
        login=payload.login,
        password=payload.password,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )
