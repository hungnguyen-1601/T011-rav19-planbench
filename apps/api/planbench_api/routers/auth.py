"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from planbench_api.approval import Role
from planbench_api.auth import User, UserDirectory, current_user, get_directory

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: Role
    username: str


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    directory: UserDirectory = get_directory(request)
    user = directory.authenticate(form.username, form.password)
    token, expires_in = directory.issue_token(user)
    return TokenResponse(
        access_token=token, expires_in=expires_in, role=user.role, username=user.username
    )


@router.get("/me", response_model=User)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user
