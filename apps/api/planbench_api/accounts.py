"""Accounts: a stable id, a nickname, and a role.

An earlier revision collapsed everyone to a single "member" role, with
ownership standing in for authority: whoever created a benchmark could
approve it themselves if nobody else was asked. That traded away the
one guarantee the platform exists to make — a benchmark result was
seen by someone other than the person who produced it — for the
convenience of not having to keep two accounts around locally.

So there are two roles again: :class:`UserRole.ENGINEER` runs
benchmarks, :class:`UserRole.APPROVER` reviews them. A review may only
be requested from an Approver; an Engineer cannot self-approve their
own work (see :mod:`planbench_api.approval`). ``is_admin`` is a
separate, orthogonal override for operational recovery — not a third
role — and every action taken through it is recorded distinctly in the
audit trail from an ordinary approval, so a reader can always tell
whether a result was actually reviewed or just unblocked by an admin.

Two identifiers, deliberately not interchangeable:

* ``id`` is what authorization uses. It never changes.
* ``nickname`` is what people type to find each other. It is unique
  case-insensitively, and it is *only* a lookup key — resolving a
  nickname yields an id, and every permission check uses the id.

Nicknames are mutable in principle; ids are not. Keying permissions on
the mutable one would mean a rename silently reassigns authority.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

NICKNAME_MIN = 3
NICKNAME_MAX = 30
#: Letters, digits, underscore, hyphen. No whitespace, no case folding
#: surprises, nothing that needs escaping in a URL.
NICKNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

NICKNAME_RULES = (
    f"{NICKNAME_MIN}–{NICKNAME_MAX} characters, letters, digits, "
    "underscore or hyphen only, no spaces"
)


class AuthProvider(StrEnum):
    GOOGLE = "google"
    GITHUB = "github"


class UserRole(StrEnum):
    """Who a member is for approval purposes — separate from ``is_admin``.

    Only two values: a benchmark needs someone who ran it (any member) and
    someone else who reviews it, and only an :class:`UserRole.APPROVER`
    may be named as that reviewer. ``is_admin`` is not a third value here
    — it is an orthogonal override capability, checked independently
    wherever a role is checked.
    """

    ENGINEER = "engineer"
    APPROVER = "approver"


class AccountError(ValueError):
    """Something about this account cannot be done as asked."""


class NicknameError(AccountError):
    """The nickname is malformed or already taken."""


class AccountLinkError(AccountError):
    """This provider identity belongs to a different PlanBench account.

    Distinct from :class:`NicknameError` because the sign-in callback has
    to be able to tell the person *why* linking failed — "already linked
    to another account, sign in with it instead" is actionable, and a
    generic failure is not.
    """


def normalise_nickname(nickname: str) -> str:
    """The comparison key: case-folded, whitespace-trimmed.

    Stored alongside the display form so uniqueness can be enforced by a
    plain unique index — portable across SQLite and PostgreSQL, unlike a
    functional index on ``lower()``.
    """
    return nickname.strip().casefold()


def validate_nickname(nickname: str) -> str:
    """Return the cleaned nickname, or raise :class:`NicknameError`."""
    cleaned = nickname.strip()
    if not cleaned:
        raise NicknameError("nickname is required")
    if len(cleaned) < NICKNAME_MIN or len(cleaned) > NICKNAME_MAX:
        raise NicknameError(
            f"nickname must be {NICKNAME_MIN}–{NICKNAME_MAX} characters, got {len(cleaned)}"
        )
    if not NICKNAME_PATTERN.match(cleaned):
        raise NicknameError(f"nickname may only contain {NICKNAME_RULES}")
    return cleaned


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class User(BaseModel):
    """A member of the platform.

    ``nickname`` is empty for an account created by OAuth that has not
    finished onboarding yet. Everything except choosing a nickname is
    blocked until it is set, because a member with no nickname cannot be
    named in a review request and would be invisible to everyone else.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    nickname: str = ""
    email: str = ""
    display_name: str = ""
    avatar_url: str = ""
    is_admin: bool = False
    role: UserRole = UserRole.ENGINEER
    created_at: str = ""
    updated_at: str = ""

    @property
    def needs_nickname(self) -> bool:
        return not self.nickname

    @property
    def label(self) -> str:
        """What to show in an audit entry: the nickname, else the id."""
        return self.nickname or self.id


class StoredUser(BaseModel):
    """A user plus the credential material the public model omits."""

    model_config = ConfigDict(frozen=True)

    user: User
    nickname_key: str = ""
    #: Only set for accounts that can use the development password login.
    password_hash: str | None = None

    def public(self) -> User:
        return self.user


class OAuthAccount(BaseModel):
    """A provider identity linked to exactly one PlanBench account.

    ``provider`` + ``provider_account_id`` is unique: an identity belongs
    to one account, so two people cannot end up sharing one login.

    ``provider_email`` is stored for display and support, never for
    matching. Two accounts sharing an email address are still two
    accounts — see :mod:`planbench_api.oauth` for why.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    user_id: str
    provider: AuthProvider
    provider_account_id: str
    provider_email: str = ""
    created_at: str = ""
    updated_at: str = ""


class UserSummary(BaseModel):
    """The public view of somebody else — no email, no admin flag.

    Nickname search is open to every signed-in member, so it must not
    become a way to harvest addresses.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    nickname: str
    display_name: str = ""
    avatar_url: str = ""
    role: UserRole = UserRole.ENGINEER

    @staticmethod
    def of(user: User) -> UserSummary:
        return UserSummary(
            id=user.id,
            nickname=user.nickname,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=user.role,
        )


__all__ = [
    "NICKNAME_MAX",
    "NICKNAME_MIN",
    "NICKNAME_RULES",
    "AccountError",
    "AccountLinkError",
    "AuthProvider",
    "NicknameError",
    "OAuthAccount",
    "StoredUser",
    "User",
    "UserRole",
    "UserSummary",
    "normalise_nickname",
    "now_iso",
    "validate_nickname",
]
