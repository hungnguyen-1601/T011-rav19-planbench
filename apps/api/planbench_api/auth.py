"""Authentication: who the caller is, and which capabilities that buys.

Two questions, deliberately kept apart in one module because they share
one thing — the token — and nothing else. ``decode_token`` answers *who*;
``require_capability`` answers *what kind of action*. Neither answers
*which record*: ownership does that, at the call site, and both
conditions have to hold (HĐ-14.1).

``require_roles`` is not coming back. A dependency that names roles
spreads the role table across every router, so the day a capability
moves between packages is the day somebody greps for it and misses one.
Routes name the **capability** they need; the mapping from role to
capability lives in exactly one dict here.

Capability packages do not nest. ``reviewer`` is not ``engineer`` plus
extras — it lacks ``resource.write`` and ``run.create`` on purpose, and
``admin`` holds no business capability at all. A person who needs two
packages holds two roles; the audit trail records which capability
authorised each action, not the caller's highest-ranked role, because
"highest" is not a thing here.

**The token carries a user id, never a nickname.** Nicknames are how
people find each other and they can be changed; an authorization key
that a user can change is not an authorization key. ``sub`` is the
immutable account id and every permission check resolves through it.

**Secrets come from the environment.** ``AUTH_SECRET`` signs tokens and
the OAuth state cookie. Unset, a random per-process secret is generated:
development stays frictionless, tokens simply do not survive a restart,
and nothing is ever committed. Production must set it — docs/reference/DEPLOYMENT.md.

**Password login is opt-in.** ``PLANBENCH_ENABLE_DEV_LOGIN=true`` turns
it on; otherwise the endpoint refuses and the login page does not show
it. A password path that is on by default is one that gets left on.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict

from planbench_api.accounts import (
    Capability,
    NicknameError,
    Role,
    User,
    roles_granting,
)
from planbench_api.config import Settings
from planbench_api.deployment import DeploymentPolicy, load_policy, parse_seed_roles
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

    def __init__(
        self,
        settings: Settings,
        users: UserRepositoryPort,
        policy: DeploymentPolicy | None = None,
    ) -> None:
        self._users = users
        self._secret = settings.auth_secret or settings.jwt_secret or secrets.token_urlsafe(48)
        self._token_ttl = timedelta(minutes=settings.jwt_ttl_minutes)
        self._dev_login = settings.enable_dev_login
        self._policy = policy or load_policy(settings)
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
                nickname, roles, password = _parse_seed_entry(entry)
                self._ensure_password_user(
                    nickname, password, parse_seed_roles(roles, self._policy.profile)
                )
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

    def _ensure_password_user(
        self, nickname: str, password: str, roles: frozenset[Role] = frozenset()
    ) -> User | None:
        """Create the account, or bring an existing one back in step.

        **Roles are reconciled the same way the password is, and that is
        what carries an installed copy across an upgrade.** A desktop
        install created its account long before roles existed; nothing
        else would ever grant them, so the account the person signs in
        with every day would come back from the update holding nothing.
        Reconciling here — on the profiles that state roles in their
        configuration — means the upgrade is invisible to them, which is
        the only acceptable outcome for a copy somebody else is using.

        It **adds** what is missing and never removes what an
        administrator granted through the UI: configuration describes a
        floor, not a ceiling.

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
            self._reconcile_seed_roles(existing, roles)
            return None
        try:
            return self._users.create(
                nickname=nickname,
                display_name=nickname,
                roles=self._roles_at_creation(nickname, roles),
                password_hash=hash_password(password),
            )
        except NicknameError as exc:
            # A malformed seed entry should not stop the API booting; the
            # rest of the sign-in paths are unaffected.
            logger.warning("skipping seed user %r: %s", nickname, exc)
            return None

    def _roles_at_creation(self, nickname: str, roles: frozenset[Role]) -> frozenset[Role]:
        """What a seeded account is born with.

        The entry's own roles, plus ``admin`` when the deployment listed
        this nickname as one — ``PLANBENCH_ADMIN_NICKNAMES`` predates the
        seed roles field and installed copies still carry it, so it has
        to keep meaning what it meant. Falls back to the default grant
        when the entry says nothing, so an account is never created with
        no capability at all.
        """
        granted = set(roles)
        if nickname.casefold() in self._admin_nicknames:
            granted.add(Role.ADMIN)
        if not granted:
            granted.update(self._policy.default_roles)
        return frozenset(granted)

    def _reconcile_seed_roles(self, user: User, roles: frozenset[Role]) -> None:
        """Add the profile's roles to an account that predates them."""
        if not roles or not self._policy.reconciles_seed_roles:
            return
        missing = roles - user.roles
        if not missing:
            return
        self._users.set_roles(
            user.id,
            user.roles | missing,
            reason=f"reconciled from the {self._policy.profile.value} deployment profile",
        )
        logger.info(
            "granted seed account the roles its deployment profile states",
            extra={
                "context": {
                    "nickname": user.nickname,
                    "granted": sorted(role.value for role in missing),
                    "profile": self._policy.profile.value,
                }
            },
        )

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
        # Stamped here rather than at each sign-in route, because this is
        # the one place every route that hands out a session goes
        # through — password, OAuth exchange, and whatever comes next.
        # Failure to record it must not cost somebody their sign-in: the
        # column exists to fill a column in an administrator's table, and
        # that is not worth an outage.
        try:
            self._users.record_sign_in(user.id)
        except Exception:  # noqa: BLE001 - never block a sign-in over bookkeeping
            logger.warning("could not record the sign-in time", exc_info=True)
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
            # Read through to storage every time: a deleted account, a
            # renamed one, or one whose roles changed a minute ago must
            # not keep acting on a stale token body.
            user = self._users.get(str(user_id))
        except NotFoundError as exc:
            raise AuthError("this account no longer exists") from exc
        if user.disabled:
            # Checked here rather than at each route, because a disabled
            # account has to stop being able to do anything at all —
            # including the reads that carry no capability check.
            raise AuthError("this account has been disabled")
        return user


def _parse_seed_entry(entry: str) -> tuple[str, str, str]:
    """``name:roles:password``, or ``name:password``.

    Returns ``(nickname, roles, password)`` with ``roles`` empty for the
    two-part form.

    **The middle field means something again.** It was in the original
    format, then spent a release being parsed and thrown away — the
    roleless period had nothing to do with it. Reviving it rather than
    inventing a fourth variable keeps one line describing one account,
    which matters on a desktop install where three of them sit in a
    template: `admin:engineer+reviewer+admin:admin`.

    Roles are joined with ``+`` because ``,`` already separates entries
    and ``:`` already separates fields. Which roles are honoured is a
    question about the deployment profile, answered in
    :func:`planbench_api.deployment.parse_seed_roles`, not here.
    """
    parts = entry.strip().split(":")
    if len(parts) == 2:
        return parts[0].strip(), "", parts[1]
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), ":".join(parts[2:])
    raise ValueError(
        f"PLANBENCH_SEED_USERS entry {entry!r} must be 'name:password' or 'name:roles:password'"
    )


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


def _holders_of(capability: Capability, users: UserRepositoryPort) -> list[str]:
    """Nicknames a caller could ask, for the refusal message.

    Capped, and it names people rather than roles alone, because "ask an
    administrator" is not actionable in a deployment where the person
    reading it does not know who that is.
    """
    names: set[str] = set()
    for role in roles_granting(capability):
        for holder in users.list_with_role(role):
            if holder.nickname and not holder.disabled:
                names.add(holder.nickname)
    return sorted(names)[:5]


def require_capability(capability: Capability) -> Callable[..., User]:
    """A dependency that admits callers holding ``capability``.

    Routes name the capability, never the role. The mapping lives in one
    dict in :mod:`planbench_api.accounts`, so moving a capability between
    packages is a two-line diff there rather than a search through every
    router — and the day somebody misses one of those greps is the day a
    route keeps admitting a package that no longer owns the action.

    This is authorisation's *first* condition. Ownership is the second,
    and it stays at the call site: only the route knows which record the
    caller is reaching for.
    """

    def dependency(request: Request, user: ActiveUser) -> User:
        if user.can(capability):
            return user
        packages = ", ".join(role.value for role in roles_granting(capability)) or "no role"
        message = f"this needs the {packages} role"
        holders = _holders_of(capability, request.app.state.repos.users)
        if holders:
            message += f". Members who hold it: {', '.join(holders)}"
        raise Forbidden(message)

    return dependency


#: Ready-made dependencies for the capabilities used across many routers.
#: Declared here so a router writes ``user: ReadingUser`` rather than
#: repeating the ``Annotated[...]`` spelling at every endpoint.
ReadingUser = Annotated[User, Depends(require_capability(Capability.RESOURCE_READ))]
WritingUser = Annotated[User, Depends(require_capability(Capability.RESOURCE_WRITE))]
SimulatingUser = Annotated[User, Depends(require_capability(Capability.SIMULATION_RUN))]
CataloguingUser = Annotated[User, Depends(require_capability(Capability.ALGORITHM_CATALOGUE))]
