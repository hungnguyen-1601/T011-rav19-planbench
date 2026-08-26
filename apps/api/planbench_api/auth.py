"""Authentication: who the caller is. Not what they may do.

Authorization moved out of this module in the accounts refactor. There
is no ``require_roles`` any more, because there are no roles to require:
every signed-in person is a member, and what they may do depends on the
benchmark in front of them (see :mod:`planbench_api.approval`). Keeping
a role check here would have been a second, weaker answer to a question
that ownership already answers.

**The token carries a user id, never a nickname.** Nicknames are how
people find each other and they can be changed; an authorization key
that a user can change is not an authorization key. ``sub`` is the
immutable account id and every permission check resolves through it.

**Secrets come from the environment.** ``AUTH_SECRET`` signs tokens and
the OAuth state cookie. Unset, a random per-process secret is generated:
development stays frictionless, tokens simply do not survive a restart,
and nothing is ever committed. Production must set it — docs/DEPLOYMENT.md.

**Password login is opt-in.** ``PLANBENCH_ENABLE_DEV_LOGIN=true`` turns
it on; otherwise the endpoint refuses and the login page does not show
it. A password path that is on by default is one that gets left on.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict

from planbench_api.accounts import NicknameError, User
from planbench_api.config import Settings
from planbench_api.errors import NotFoundError
from planbench_api.repository_ports import UserRepositoryPort

logger = logging.getLogger("planbench.api.auth")

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# bcrypt hashes at most 72 bytes; longer passwords are truncated by the
# algorithm itself, so truncate explicitly to keep hash/verify consistent.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:_BCRYPT_MAX_BYTES], password_hash.encode())


class AuthError(Exception):
    """Authentication failed (bad credentials, or a bad/absent token)."""


class Forbidden(Exception):
    """Authenticated, but not permitted to do this."""


class TokenPayload(BaseModel):
    """What a PlanBench JWT actually contains."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    expires_in: int


class AuthService:
    """Issues and verifies tokens; owns the dev-login password path.

    Accounts themselves live in the user repository, so this class holds
    no user state: two workers sharing a database agree about who exists,
    which the previous in-memory directory could not manage.
    """

    def __init__(self, settings: Settings, users: UserRepositoryPort) -> None:
        self._users = users
        self._secret = settings.auth_secret or settings.jwt_secret or secrets.token_urlsafe(48)
        self._token_ttl = timedelta(minutes=settings.jwt_ttl_minutes)
        self._dev_login = settings.enable_dev_login
        self._admin_nicknames = frozenset(
            part.strip().casefold() for part in settings.admin_nicknames.split(",") if part.strip()
        )
        self._seed_users(settings)

    @property
    def secret(self) -> str:
        """Also signs the OAuth state cookie — one secret, one rotation."""
        return self._secret

    @property
    def dev_login_enabled(self) -> bool:
        return self._dev_login

    # -- seeding -------------------------------------------------------

    def _seed_users(self, settings: Settings) -> None:
        """Provision password accounts, but only when dev login is on.

        Creating them regardless would leave password hashes for accounts
        nobody can reach — dormant credentials that outlive the reason
        they were created.
        """
        if not self._dev_login:
            return
        entries = [entry for entry in settings.seed_users.split(",") if entry.strip()]
        if entries:
            for entry in entries:
                nickname, password = _parse_seed_entry(entry)
                self._ensure_password_user(nickname, password)
            return
        # Fresh checkout: one usable account, password generated per
        # process and logged once. Never hardcoded, never persisted to a
        # tracked file.
        password = secrets.token_urlsafe(12)
        if self._ensure_password_user("developer", password) is not None:
            logger.warning(
                "development login enabled; generated a password for 'developer' "
                "(set PLANBENCH_SEED_USERS to control it)",
                extra={"context": {"nickname": "developer"}},
            )
            # The password itself goes out separately so the line above
            # stays safe to keep in a log aggregator.
            logger.warning("developer password: %s", password)

    def _ensure_password_user(self, nickname: str, password: str) -> User | None:
        """Create the account, or bring an existing one back in step.

        Returns the account only when it was *created*, so the caller can
        tell a fresh deployment from a returning one.

        **The password is reconciled rather than left alone**, and that
        is a correction. Creating-only meant `PLANBENCH_SEED_USERS` was
        read exactly once in an installation's life: change the entry
        afterwards and the file said one password while the database
        still held the hash of another, with the sign-in page rejecting
        the credential printed right next to it. That is what happened
        when the desktop build moved to a known password — `.env` read
        `admin:admin`, the account had been created days earlier with a
        generated one, and there was no way to tell from the outside.

        Safe because the seed list is deployment configuration and there
        is no other way to set a password: the API has no change-password
        route, so nothing a person did through the app can be undone by
        this.
        """
        existing = self._users.find_by_nickname(nickname)
        if existing is not None:
            stored = self._users.get_stored(existing.id)
            if not verify_password(password, stored.password_hash or ""):
                self._users.set_password(existing.id, hash_password(password))
                logger.info(
                    "seed account password brought in step with PLANBENCH_SEED_USERS",
                    extra={"context": {"nickname": nickname}},
                )
            return None
        try:
            return self._users.create(
                nickname=nickname,
                display_name=nickname,
                is_admin=nickname.casefold() in self._admin_nicknames,
                password_hash=hash_password(password),
            )
        except NicknameError as exc:
            # A malformed seed entry should not stop the API booting; the
            # rest of the sign-in paths are unaffected.
            logger.warning("skipping seed user %r: %s", nickname, exc)
            return None

    # -- sign-in -------------------------------------------------------

    def authenticate(self, nickname: str, password: str) -> User:
        if not self._dev_login:
            raise AuthError(
                "password sign-in is disabled; use Google or GitHub "
                "(set PLANBENCH_ENABLE_DEV_LOGIN=true for local development)"
            )
        user = self._users.find_by_nickname(nickname)
        stored = None
        if user is not None:
            stored = self._users.get_stored(user.id)
        # Same message either way: distinguishing "no such user" from
        # "wrong password" tells an attacker which nicknames exist.
        if stored is None or not stored.password_hash:
            raise AuthError("invalid username or password")
        if not verify_password(password, stored.password_hash):
            raise AuthError("invalid username or password")
        return stored.user

    def issue_token(self, user: User) -> tuple[str, int]:
        expires_at = datetime.now(UTC) + self._token_ttl
        payload = {"sub": user.id, "exp": expires_at}
        token = jwt.encode(payload, self._secret, algorithm=ALGORITHM)
        return token, int(self._token_ttl.total_seconds())

    def decode_token(self, token: str) -> User:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token expired") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("invalid token") from exc
        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("malformed token payload")
        try:
            # Read through to storage every time: a deleted account, or a
            # renamed one, must not keep acting on a stale token body.
            return self._users.get(str(user_id))
        except NotFoundError as exc:
            raise AuthError("this account no longer exists") from exc


def _parse_seed_entry(entry: str) -> tuple[str, str]:
    """``name:password``, or the legacy ``name:role:password``.

    The role field is accepted and discarded so an existing deployment's
    PLANBENCH_SEED_USERS keeps working after the refactor.
    """
    parts = entry.strip().split(":")
    if len(parts) == 2:
        return parts[0].strip(), parts[1]
    if len(parts) >= 3:
        return parts[0].strip(), ":".join(parts[2:])
    raise ValueError(f"PLANBENCH_SEED_USERS entry {entry!r} must be 'name:password'")


def get_auth(request: Request) -> AuthService:
    return request.app.state.auth


def current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> User:
    """Resolve the caller from the bearer token; raises AuthError if absent."""
    if not token:
        raise AuthError("missing bearer token")
    return get_auth(request).decode_token(token)


CurrentUser = Annotated[User, Depends(current_user)]


def require_nickname(user: CurrentUser) -> User:
    """A caller who has finished onboarding.

    Everything except the nickname endpoints needs this: a member with no
    nickname cannot be named as a reviewer, so letting them create work
    would produce benchmarks nobody can send anywhere.
    """
    if user.needs_nickname:
        raise Forbidden("choose a nickname before using PlanBench")
    return user


ActiveUser = Annotated[User, Depends(require_nickname)]
