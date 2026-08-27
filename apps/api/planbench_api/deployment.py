"""What kind of deployment this is, and what that permits.

Three profiles, and the difference between them is not cosmetic — each
one answers "may a single person approve their own work?" and "may an
account hold every capability at once?" differently, so the answer has
to be stated rather than inferred.

**Absent means production.** A server already running today has no
``PLANBENCH_DEPLOYMENT_PROFILE`` in its environment, and the reading of
silence that keeps it safe is the strict one. The desktop launcher does
not rely on its ``.env`` for this: it sets the profile in-process before
:class:`~planbench_api.config.Settings` is constructed, so a copy
installed months ago, whose ``.env`` predates this variable, still
identifies itself as a desktop install. That ordering is the whole
reason an upgrade in place does not quietly demote the one account the
person signs in with.

**The guards fail closed and fail loud.** A production deployment that
still carries a demo owner refuses to start rather than starting with a
superuser nobody remembered. Refusing at boot is recoverable in a way
that a silent superuser is not.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from planbench_api.accounts import BUSINESS_ROLES, Role

logger = logging.getLogger("planbench.api.deployment")


class DeploymentProfile(StrEnum):
    #: A server several people share. Strict separation of duties, no
    #: ``demo_owner``, roles granted deliberately.
    PRODUCTION = "production"
    #: The packaged Windows app: one machine, one person, dev login. The
    #: seeded account carries the three business packages so the whole
    #: workflow is reachable, and relaxed duties let them finish it.
    DESKTOP_SINGLE_USER = "desktop-single-user"
    #: A presentation machine. One ``demo_owner`` holds everything, and
    #: the page says so in a banner that cannot be dismissed.
    DEMO = "demo"


class SeparationOfDuties(StrEnum):
    STRICT = "strict"
    RELAXED = "relaxed"


class DeploymentError(RuntimeError):
    """The deployment is configured in a way that must not be started."""


#: Profiles where one person legitimately holds both ends of a review.
_SINGLE_PERSON_PROFILES = frozenset({DeploymentProfile.DESKTOP_SINGLE_USER, DeploymentProfile.DEMO})


def parse_profile(value: str) -> DeploymentProfile:
    """Read the configured profile, refusing anything unrecognised.

    A typo must not fall back to a permissive profile, and it must not
    fall back to a strict one either without saying so — either way the
    deployment would be running under rules nobody chose.
    """
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return DeploymentProfile.PRODUCTION
    try:
        return DeploymentProfile(cleaned)
    except ValueError as exc:
        allowed = ", ".join(profile.value for profile in DeploymentProfile)
        raise DeploymentError(
            f"PLANBENCH_DEPLOYMENT_PROFILE={value!r} is not a deployment profile "
            f"(expected one of: {allowed})"
        ) from exc


def parse_separation_of_duties(value: str, profile: DeploymentProfile) -> SeparationOfDuties:
    """Read the duties setting and refuse the combination that lies.

    ``relaxed`` on a shared server is the one combination worth blocking
    at boot: it turns every approval on that deployment into something
    the person who ran the experiment could have produced alone, and it
    does so without any single action looking wrong.
    """
    cleaned = (value or "").strip().lower() or SeparationOfDuties.STRICT.value
    try:
        setting = SeparationOfDuties(cleaned)
    except ValueError as exc:
        raise DeploymentError(
            f"PLANBENCH_SEPARATION_OF_DUTIES={value!r} must be 'strict' or 'relaxed'"
        ) from exc
    if setting is SeparationOfDuties.RELAXED and profile not in _SINGLE_PERSON_PROFILES:
        raise DeploymentError(
            "PLANBENCH_SEPARATION_OF_DUTIES=relaxed is only available to a single-person "
            f"deployment ({', '.join(sorted(p.value for p in _SINGLE_PERSON_PROFILES))}); "
            f"this one is {profile.value!r}"
        )
    return setting


def parse_default_roles(value: str) -> frozenset[Role]:
    """What a brand-new account is granted.

    Only ``engineer``, or nothing. Reviewer and admin are refused here
    rather than trimmed silently: a deployment that thought it was
    handing out reviewer to every sign-up should be told, not corrected
    behind its back.
    """
    names = [part.strip().lower() for part in (value or "").split(",") if part.strip()]
    roles: set[Role] = set()
    for name in names:
        try:
            role = Role(name)
        except ValueError as exc:
            allowed = ", ".join(role.value for role in BUSINESS_ROLES)
            raise DeploymentError(
                f"PLANBENCH_DEFAULT_ROLES={value!r} names {name!r}, which is not a role "
                f"(expected: {allowed})"
            ) from exc
        if role is not Role.ENGINEER:
            raise DeploymentError(
                f"PLANBENCH_DEFAULT_ROLES may only contain 'engineer'; {role.value!r} is a "
                "grant somebody makes deliberately, not one a sign-up form hands out"
            )
        roles.add(role)
    return frozenset(roles)


def parse_seed_roles(value: str, profile: DeploymentProfile) -> frozenset[Role]:
    """Roles named in a ``PLANBENCH_SEED_USERS`` entry.

    Ignored with a warning on a shared server: seed accounts exist so a
    single-person install has something to sign in as, and a production
    deployment that grew a reviewer out of an environment variable would
    have grown it silently.

    ``demo_owner`` is never accepted here. It is bound by identity —
    a verified email, or the nickname of an account the deployment
    created itself — not by a line that also carries a password.
    """
    names = [part.strip().lower() for part in (value or "").split("+") if part.strip()]
    roles: set[Role] = set()
    for name in names:
        try:
            role = Role(name)
        except ValueError:
            logger.warning("seed entry names an unknown role %r; ignoring it", name)
            continue
        if role is Role.DEMO_OWNER:
            logger.warning(
                "seed entry names demo_owner; ignoring it — the demo owner is bound by "
                "PLANBENCH_DEMO_OWNER_EMAIL or PLANBENCH_DEMO_OWNER_NICKNAME"
            )
            continue
        roles.add(role)
    if roles and profile is DeploymentProfile.PRODUCTION:
        logger.warning(
            "ignoring roles %s from PLANBENCH_SEED_USERS: this deployment is 'production', "
            "where roles are granted through /admin/users rather than by configuration",
            ",".join(sorted(role.value for role in roles)),
        )
        return frozenset()
    return frozenset(roles)


class DeploymentPolicy:
    """The parsed, validated answers, resolved once at startup."""

    def __init__(
        self,
        *,
        profile: DeploymentProfile,
        separation_of_duties: SeparationOfDuties,
        default_roles: frozenset[Role],
        demo_owner_email: str = "",
        demo_owner_nickname: str = "",
    ) -> None:
        self.profile = profile
        self.separation_of_duties = separation_of_duties
        self.default_roles = default_roles
        self.demo_owner_email = demo_owner_email.strip().casefold()
        self.demo_owner_nickname = demo_owner_nickname.strip().casefold()

    @property
    def relaxed(self) -> bool:
        return self.separation_of_duties is SeparationOfDuties.RELAXED

    @property
    def is_demo(self) -> bool:
        return self.profile is DeploymentProfile.DEMO

    @property
    def is_desktop(self) -> bool:
        return self.profile is DeploymentProfile.DESKTOP_SINGLE_USER

    @property
    def reconciles_seed_roles(self) -> bool:
        """Whether seeded accounts get their roles re-applied on boot.

        True for the single-person profiles, and that is what carries an
        installed copy across an upgrade: the account exists already, the
        roles are new, and nothing else would ever grant them.
        """
        return self.profile in _SINGLE_PERSON_PROFILES

    def describe(self) -> str:
        return (
            f"profile={self.profile.value} separation_of_duties={self.separation_of_duties.value}"
        )


def load_policy(settings) -> DeploymentPolicy:
    """Build the policy from settings, refusing an impossible combination."""
    profile = parse_profile(settings.deployment_profile)
    duties = parse_separation_of_duties(settings.separation_of_duties, profile)
    demo_email = settings.demo_owner_email
    demo_nickname = settings.demo_owner_nickname
    if profile is not DeploymentProfile.DEMO and (demo_email or demo_nickname):
        raise DeploymentError(
            "PLANBENCH_DEMO_OWNER_EMAIL / PLANBENCH_DEMO_OWNER_NICKNAME are set, but this "
            f"deployment is {profile.value!r}. The demo owner holds every capability at "
            "once and exists only under the 'demo' profile"
        )
    return DeploymentPolicy(
        profile=profile,
        separation_of_duties=duties,
        default_roles=parse_default_roles(settings.default_roles),
        demo_owner_email=demo_email,
        demo_owner_nickname=demo_nickname,
    )


def guard_stored_state(policy: DeploymentPolicy, users) -> None:
    """Refuse to serve a production deployment that still holds a demo owner.

    Checked against storage rather than against configuration, because
    the dangerous case is precisely the one where the configuration was
    already cleaned up and the grant was not: ``.env`` reads
    ``production``, and one account in the database still carries every
    capability there is.
    """
    if policy.profile is DeploymentProfile.DEMO:
        return
    holders = users.list_with_role(Role.DEMO_OWNER)
    active = [user for user in holders if not user.disabled]
    if not active:
        return
    named = ", ".join(sorted(user.label for user in active))
    raise DeploymentError(
        f"the demo owner role is still assigned to {named}, and this deployment is "
        f"{policy.profile.value!r}. Run the removal procedure in docs/DEMO-PROFILE.md "
        "before serving it: grant that account real roles, revoke demo_owner, then start"
    )


__all__ = [
    "DeploymentError",
    "DeploymentPolicy",
    "DeploymentProfile",
    "SeparationOfDuties",
    "guard_stored_state",
    "load_policy",
    "parse_default_roles",
    "parse_profile",
    "parse_seed_roles",
    "parse_separation_of_duties",
]
