"""JWT authentication and role-based access control.

Secrets come from the environment (``PLANBENCH_JWT_SECRET``). If it is
unset, a random per-process secret is generated: development stays
frictionless while tokens never survive a restart, and no secret is ever
committed. Production deployments must set the variable — see
docs/DEPLOYMENT.md.

Seed users are provisioned from ``PLANBENCH_SEED_USERS`` (a
``name:role:password`` list). The built-in fallback exists so a fresh
checkout is usable; the password is generated at startup and logged
once, never hardcoded.
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

from planbench_api.approval import Role
from planbench_api.config import Settings

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


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    role: Role


class StoredUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    role: Role
    password_hash: str


class AuthError(Exception):
    """Authentication failed (bad credentials or token)."""


class Forbidden(Exception):
    """Authenticated, but the role is not permitted."""


class UserDirectory:
    """In-memory user store (PostgreSQL-backed in a later milestone)."""

    def __init__(self, settings: Settings) -> None:
        self._users: dict[str, StoredUser] = {}
        self._secret = settings.jwt_secret or secrets.token_urlsafe(48)
        self._token_ttl = timedelta(minutes=settings.jwt_ttl_minutes)
        self._load_seed_users(settings)

    def _load_seed_users(self, settings: Settings) -> None:
        entries = [entry for entry in settings.seed_users.split(",") if entry.strip()]
        if entries:
            for entry in entries:
                try:
                    username, role, password = entry.split(":", 2)
                except ValueError:
                    raise ValueError(
                        f"PLANBENCH_SEED_USERS entry {entry!r} must be 'name:role:password'"
                    ) from None
                self.add(username.strip(), Role(role.strip()), password)
            return
        # Development fallback: random passwords, logged once, never stored
        # in source or version control.
        for username, role in (("operator", Role.OPERATOR), ("reviewer", Role.REVIEWER)):
            password = secrets.token_urlsafe(12)
            self.add(username, role, password)
            logger.warning(
                "generated development credentials (set PLANBENCH_SEED_USERS to control them)",
                extra={"context": {"username": username, "password": password}},
            )

    def add(self, username: str, role: Role, password: str) -> StoredUser:
        user = StoredUser(username=username, role=role, password_hash=hash_password(password))
        self._users[username] = user
        return user

    def authenticate(self, username: str, password: str) -> User:
        stored = self._users.get(username)
        if stored is None or not verify_password(password, stored.password_hash):
            raise AuthError("invalid username or password")
        return User(username=stored.username, role=stored.role)

    def issue_token(self, user: User) -> tuple[str, int]:
        expires_at = datetime.now(UTC) + self._token_ttl
        payload = {"sub": user.username, "role": user.role.value, "exp": expires_at}
        token = jwt.encode(payload, self._secret, algorithm=ALGORITHM)
        return token, int(self._token_ttl.total_seconds())

    def decode_token(self, token: str) -> User:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token expired") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("invalid token") from exc
        username = payload.get("sub")
        role = payload.get("role")
        if not username or role not in {r.value for r in Role}:
            raise AuthError("malformed token payload")
        return User(username=username, role=Role(role))


def get_directory(request: Request) -> UserDirectory:
    return request.app.state.users


def current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> User:
    """Resolve the caller from the bearer token; raises AuthError if absent."""
    if not token:
        raise AuthError("missing bearer token")
    return get_directory(request).decode_token(token)


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role):
    """Dependency factory enforcing that the caller holds one of ``roles``."""

    def dependency(user: CurrentUser) -> User:
        if user.role is not Role.ADMIN and user.role not in roles:
            raise Forbidden(
                f"role {user.role.value!r} may not access this endpoint "
                f"(allowed: {sorted(role.value for role in roles)})"
            )
        return user

    return dependency
