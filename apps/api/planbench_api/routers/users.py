"""Nicknames: choosing your own, and finding other members by theirs.

Search returns a deliberately thin view — nickname, display name,
avatar. No email, no admin flag. Anyone signed in can look up anyone, so
what comes back is only what is needed to address a review request to
the right person.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from planbench_api.account_service import AccountService
from planbench_api.accounts import NicknameError, UserSummary, validate_nickname
from planbench_api.auth import CurrentUser
from planbench_api.config import get_settings
from planbench_api.routers.auth import UserResource, _resource

router = APIRouter(prefix="/users", tags=["users"])


class NicknameRequest(BaseModel):
    nickname: str


class NicknameCheck(BaseModel):
    nickname: str
    available: bool
    valid: bool
    message: str = ""


def _accounts(request: Request) -> AccountService:
    settings = get_settings()
    return AccountService(
        request.app.state.repos.users,
        admin_nicknames=settings.admin_nicknames,
        admin_emails=settings.admin_emails,
        policy=getattr(request.app.state, "deployment", None),
    )


@router.get("/search", response_model=list[UserSummary])
def search_users(request: Request, nickname: str, _: CurrentUser) -> list[UserSummary]:
    """Prefix search, for the reviewer autocomplete."""
    return [UserSummary.of(user) for user in _accounts(request).search(nickname)]


@router.get("/nickname-available", response_model=NicknameCheck)
def check_nickname(request: Request, nickname: str, _: CurrentUser) -> NicknameCheck:
    """Live feedback for the onboarding screen.

    Invalid and taken are answered the same way — as a message, not an
    error — because this endpoint is called on every keystroke and a 422
    per character would be noise in the console and in the logs.
    """
    try:
        validate_nickname(nickname)
    except NicknameError as exc:
        return NicknameCheck(nickname=nickname, available=False, valid=False, message=str(exc))
    available = _accounts(request).nickname_available(nickname)
    return NicknameCheck(
        nickname=nickname,
        available=available,
        valid=True,
        message="" if available else "that nickname is already taken",
    )


@router.put("/me/nickname", response_model=UserResource)
def set_nickname(request: Request, payload: NicknameRequest, user: CurrentUser) -> UserResource:
    accounts = _accounts(request)
    return _resource(accounts.choose_nickname(user, payload.nickname), accounts)
