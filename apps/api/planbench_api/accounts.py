"""Accounts: a user, identified by a stable id and a nickname.

**Roles are coming back, and this docstring is the record of why they
left and why that was wrong.** HĐ-14 as of contract 7.0.0 defines three
independent capability packages — engineer, reviewer, admin — plus a
deployment-profile exception, ``demo_owner``. The tables live in
:mod:`planbench_api.auth`; the reasoning is in
``docs/antongduy/plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md``.

The platform first split people into ``operator`` and ``reviewer``,
which forced a single person doing their own work to sign out and back
in to get past their own approval gate. The fix applied at the time was
to delete roles entirely and let **ownership** carry all authority: you
may act on what you created, and review is something you opt into by
naming another member.

That over-corrected. Ownership answers *"which record?"* and it answers
it well; it cannot answer *"which kind of action?"* — and nothing else
was answering that question either. The visible cost: any signed-in
account could approve anybody else's decision run, because the only rule
left was "not the person who created it".

So both live here now, as separate conditions on the same check:

    allowed = has_capability(user, "resource.write") and owns(user, record)

The original complaint — one person blocked by their own gate — is
answered by ``separation_of_duties``, a setting a deployment states out
loud, not by having no roles at all. On a single-person install it reads
``relaxed`` and the self-approval is recorded as ``self_approve_config``
so the trail never claims a second human looked.

Packages do **not** nest: a reviewer is not a superset of an engineer,
and an admin holds no business capability at all. Somebody who needs
both carries both roles, and each action is audited under the capability
that actually authorised it.

``is_admin`` survives as the storage-level shadow of ``admin`` in
``user_roles`` while the migration settles. It is not a benchmark role:
an admin acting on someone else's work is recorded in the audit trail
exactly like anyone else, and carries ``override`` when it is done on
their behalf.

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

    @staticmethod
    def of(user: User) -> UserSummary:
        return UserSummary(
            id=user.id,
            nickname=user.nickname,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
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
    "UserSummary",
    "normalise_nickname",
    "now_iso",
    "validate_nickname",
]
