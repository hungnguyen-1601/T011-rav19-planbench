"""Accounts: a user, identified by a stable id and a nickname.

**Roles are coming back, and this docstring is the record of why they
left and why that was wrong.** HĐ-14 as of contract 7.0.0 defines three
independent capability packages — engineer, reviewer, admin — plus a
deployment-profile exception, ``demo_owner``. The tables live in
:mod:`planbench_api.auth`; the reasoning is in
``docs/journal/antongduy/plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md``.

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

``is_admin`` is now a **read-only property** over ``roles``. Its column
is still in the table until a later migration drops it, and nothing
reads or writes it: two records of who administers a deployment is one
too many, and the copy that goes stale is always the one a grant forgot
to update. Administrator is not a business role — an admin acting on
somebody else's work is recorded in the audit trail like anyone else,
and carries ``override`` plus a reason when it is done on their behalf.

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


class Role(StrEnum):
    """A capability package. Not a rank — see :data:`CAPABILITIES`."""

    ENGINEER = "engineer"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    #: Every capability at once, one holder per database, and only under
    #: ``PLANBENCH_DEPLOYMENT_PROFILE=demo``. Exists so a demonstration
    #: has one badge and one provisioned account instead of an
    #: explanation about why one person carries three roles.
    DEMO_OWNER = "demo_owner"


#: The three packages a production deployment grants. ``DEMO_OWNER`` is
#: deliberately absent: it is a deployment-profile exception, and code
#: that iterates "the roles" should not sweep it up.
BUSINESS_ROLES: tuple[Role, ...] = (Role.ENGINEER, Role.REVIEWER, Role.ADMIN)


class Capability(StrEnum):
    """What a caller may do, independent of which record they do it to.

    Named as data rather than as booleans on ``User`` because the
    role→capability mapping has to be readable in one screen: the day a
    capability moves between packages, the diff should be two lines
    here, not a search through routers.
    """

    RESOURCE_READ = "resource.read"
    RESOURCE_WRITE = "resource.write"
    SIMULATION_RUN = "simulation.run"
    RUN_CREATE = "run.create"
    RUN_CANCEL = "run.cancel"
    RUN_SUBMIT = "run.submit"
    RUN_REVIEW = "run.review"
    RUN_WITHDRAW = "run.withdraw"
    ALGORITHM_CATALOGUE = "algorithm.catalogue"
    ALGORITHM_INSPECT = "algorithm.inspect"
    ALGORITHM_IMPORT = "algorithm.import"
    ALGORITHM_VALIDATE = "algorithm.validate"
    ALGORITHM_VALIDATION_RUN = "algorithm.validation_run"
    ALGORITHM_PUBLISH = "algorithm.publish"
    ALGORITHM_DISABLE = "algorithm.disable"
    MODEL_UPLOAD = "model.upload"
    MODEL_VALIDATE = "model.validate"
    SYSTEM_KILL_SWITCH = "system.kill_switch"
    USER_MANAGE = "user.manage"
    SYSTEM_CONFIGURE = "system.configure"
    SYSTEM_OPERATE = "system.operate"
    AUDIT_READ = "audit.read"


#: Every capability the platform defines.
#:
#: Written out rather than spelled ``"*"``: a wildcard would silently
#: hand ``demo_owner`` any capability added later, including one whose
#: author never considered a single account holding it alongside
#: everything else. ``test_roles`` asserts this equals the union of the
#: three business packages, so a new capability that nobody filed into a
#: package fails the suite instead of quietly belonging to no one.
ALL_CAPABILITIES: frozenset[Capability] = frozenset(Capability)


CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.ENGINEER: frozenset(
        {
            Capability.RESOURCE_READ,
            Capability.RESOURCE_WRITE,
            Capability.SIMULATION_RUN,
            Capability.RUN_CREATE,
            Capability.RUN_CANCEL,
            Capability.RUN_SUBMIT,
            Capability.ALGORITHM_CATALOGUE,
        }
    ),
    Role.REVIEWER: frozenset(
        {
            Capability.RESOURCE_READ,
            # A reviewer runs the bench to watch a plugin behave before
            # publishing it. Withholding this would mean asking an
            # engineer to run it for them.
            Capability.SIMULATION_RUN,
            Capability.RUN_REVIEW,
            Capability.RUN_WITHDRAW,
            Capability.ALGORITHM_CATALOGUE,
            Capability.ALGORITHM_INSPECT,
            Capability.ALGORITHM_IMPORT,
            Capability.ALGORITHM_VALIDATE,
            Capability.ALGORITHM_VALIDATION_RUN,
            Capability.ALGORITHM_PUBLISH,
            Capability.ALGORITHM_DISABLE,
            # A trained policy is an executable artefact arriving from
            # outside, the same class of thing as a plugin bundle.
            Capability.MODEL_UPLOAD,
            Capability.MODEL_VALIDATE,
            Capability.AUDIT_READ,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Capability.RESOURCE_READ,
            Capability.ALGORITHM_CATALOGUE,
            # Turning an algorithm off is an incident action, and waiting
            # for a reviewer to be reachable is not an incident response.
            # Kept distinct from ``algorithm.disable`` so the audit row
            # says which of the two jobs the caller was doing.
            Capability.SYSTEM_KILL_SWITCH,
            Capability.USER_MANAGE,
            Capability.SYSTEM_CONFIGURE,
            Capability.SYSTEM_OPERATE,
            Capability.AUDIT_READ,
        }
    ),
    Role.DEMO_OWNER: ALL_CAPABILITIES,
}


def capabilities_of(roles: frozenset[Role] | set[Role] | tuple[Role, ...]) -> frozenset[Capability]:
    """The union of what these roles allow."""
    return frozenset().union(*(CAPABILITIES[role] for role in roles)) if roles else frozenset()


def roles_granting(capability: Capability) -> tuple[Role, ...]:
    """Which business packages include ``capability``, for error messages."""
    return tuple(role for role in BUSINESS_ROLES if capability in CAPABILITIES[role])


class AccountError(ValueError):
    """Something about this account cannot be done as asked."""


class NicknameError(AccountError):
    """The nickname is malformed or already taken."""


class LastAdministratorError(AccountError):
    """This change would leave nobody able to administer the deployment.

    Its own class because the caller has to answer it differently from
    every other refusal: the fix is "grant somebody else first", not
    "try again". It is raised from inside the same transaction that made
    the change, so two administrators removing each other at the same
    moment cannot both succeed.
    """


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
    #: The capability packages this account holds. Empty is legal and
    #: means "no capability at all" — an account part-way through
    #: onboarding, or one every role was revoked from.
    roles: frozenset[Role] = frozenset()
    #: Set when an administrator disabled the account. Disabled accounts
    #: keep their rows and their audit history; what they lose is the
    #: ability to exchange a token for a session.
    disabled_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def needs_nickname(self) -> bool:
        return not self.nickname

    @property
    def disabled(self) -> bool:
        return bool(self.disabled_at)

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.roles)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    @property
    def is_admin(self) -> bool:
        """Kept as a property so existing checks keep reading correctly.

        It was a stored column, and the column is still in the table
        until a later migration drops it — but nothing reads or writes
        it any more. Two places recording who is an administrator is one
        place too many, and the copy that loses is the one a role grant
        would have had to remember to update.
        """
        return Role.ADMIN in self.roles or Role.DEMO_OWNER in self.roles

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


class AccountEvent(BaseModel):
    """One append-only entry about an account.

    ``actor_roles`` and ``authorized_capability`` are snapshots. Reading
    them back through a join would let a role revoked next week rewrite
    what this entry says the caller was, which is the one thing an audit
    trail may never do.
    """

    model_config = ConfigDict(frozen=True)

    sequence: int = 0
    user_id: str
    actor_user_id: str | None = None
    actor_roles: str = ""
    authorized_capability: str = ""
    action: str
    previous: str = ""
    new: str = ""
    reason: str = ""
    #: True when an administrator acted on somebody else's behalf. Set
    #: alongside a mandatory reason, so "an admin fixed it" is a visible
    #: event rather than an invisible one.
    override: bool = False
    created_at: str = ""


def roles_label(roles: frozenset[Role] | set[Role]) -> str:
    """The stored form of a role snapshot: sorted, comma separated."""
    return ",".join(sorted(role.value for role in roles))


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
    "ALL_CAPABILITIES",
    "AccountEvent",
    "BUSINESS_ROLES",
    "CAPABILITIES",
    "NICKNAME_MAX",
    "NICKNAME_MIN",
    "NICKNAME_RULES",
    "AccountError",
    "AccountLinkError",
    "AuthProvider",
    "Capability",
    "LastAdministratorError",
    "NicknameError",
    "OAuthAccount",
    "Role",
    "StoredUser",
    "User",
    "UserSummary",
    "capabilities_of",
    "normalise_nickname",
    "now_iso",
    "roles_granting",
    "roles_label",
    "validate_nickname",
]
