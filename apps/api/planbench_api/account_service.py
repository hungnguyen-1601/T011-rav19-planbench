"""Accounts: sign-in through a provider, nicknames, account linking.

The three rules this module exists to enforce, all of them about not
letting one person end up in control of another person's account:

**A provider identity is the key, not an email address.** Sign-in looks
up ``(provider, provider_account_id)``. Two accounts with the same email
stay two accounts. Auto-merging on a shared address would mean that
whoever controls either provider account controls both — and email
addresses get reassigned, at companies and at universities, routinely.

**Linking is something a signed-in member does deliberately.** ``link``
requires an authenticated session and attaches the provider identity to
*that* account. It refuses when the identity already belongs elsewhere,
because silently moving it would sign someone out of their own history.

**Only a verified email is stored.** :func:`normalise_identity` already
drops unverified addresses, so an empty email here means "the provider
would not vouch for it", not "the provider did not send one".
"""

from __future__ import annotations

import logging

from planbench_api.accounts import (
    AccountError,
    AccountLinkError,
    AuthProvider,
    NicknameError,
    OAuthAccount,
    Role,
    User,
    validate_nickname,
)
from planbench_api.deployment import DeploymentPolicy
from planbench_api.oauth import OAuthIdentity
from planbench_api.repository_ports import UserRepositoryPort

logger = logging.getLogger("planbench.api.accounts")


def _split(value: str) -> frozenset[str]:
    return frozenset(part.strip().casefold() for part in value.split(",") if part.strip())


class AccountService:
    """Accounts, and the rules about which roles configuration may grant.

    Two grants come from the deployment rather than from a person, and
    both are re-applied on sign-in so adding a name to a list takes
    effect without a database edit:

    * ``admin`` — a nickname or verified email in the configured lists;
    * ``demo_owner`` — the single all-capability account, and only under
      the demo profile.

    Everything else is granted deliberately through ``/admin/users``, and
    **configuration only adds.** A role an administrator granted through
    the UI is never taken away by an environment variable: the two would
    then fight on every sign-in, and the variable would win by being the
    one that runs last.

    ``engineer`` and ``reviewer`` are not grantable from configuration on
    a shared server at all. A sign-up form that hands out a reviewer is a
    sign-up form that hands out the signatures.
    """

    def __init__(
        self,
        users: UserRepositoryPort,
        admin_nicknames: str = "",
        admin_emails: str = "",
        policy: DeploymentPolicy | None = None,
    ) -> None:
        self._users = users
        self._admin_nicknames = _split(admin_nicknames)
        self._admin_emails = _split(admin_emails)
        self._policy = policy

    def apply_role_policy(self, user: User) -> User:
        """Add the roles this deployment's configuration names.

        Additive on purpose (see the class docstring). The one thing it
        will *not* do is grant ``demo_owner`` to a second account: the
        database refuses that with a unique index, and reaching it would
        mean an environment variable had been pointed at somebody new
        while the old holder still existed — a silent transfer of every
        capability there is. The refusal is raised rather than logged.
        """
        wanted = set(user.roles)

        if self._admin_nicknames or self._admin_emails:
            listed = (
                bool(user.nickname) and user.nickname.casefold() in self._admin_nicknames
            ) or (bool(user.email) and user.email.casefold() in self._admin_emails)
            if listed:
                wanted.add(Role.ADMIN)

        if self._policy is not None and self._policy.is_demo and self._is_demo_owner(user):
            self._require_no_other_demo_owner(user)
            wanted.add(Role.DEMO_OWNER)

        if self._policy is not None and not wanted:
            # An account with no capability at all can sign in and see
            # nothing, which reads as a broken deployment rather than as
            # a policy. The default grant is what it is for.
            wanted.update(self._policy.default_roles)

        if wanted == set(user.roles):
            return user
        return self._users.set_roles(
            user.id,
            frozenset(wanted),
            reason="granted by deployment configuration",
        )

    def _is_demo_owner(self, user: User) -> bool:
        """Whether configuration names this account as the demo owner.

        Email first, and only an email the provider verified — the
        account model drops unverified ones, so a match here means a
        provider vouched for it. The nickname form exists for a local
        dev-login account the deployment created itself, where there is
        no provider to ask.
        """
        assert self._policy is not None
        if (
            self._policy.demo_owner_email
            and user.email
            and user.email.casefold() == self._policy.demo_owner_email
        ):
            return True
        if self._policy.demo_owner_nickname and user.nickname:
            return user.nickname.casefold() == self._policy.demo_owner_nickname
        return False

    def _require_no_other_demo_owner(self, user: User) -> None:
        holders = [
            holder for holder in self._users.list_with_role(Role.DEMO_OWNER) if holder.id != user.id
        ]
        if holders:
            named = ", ".join(sorted(holder.label for holder in holders))
            raise AccountError(
                f"the demo owner role is already held by {named}. Revoke it there before "
                "pointing PLANBENCH_DEMO_OWNER_* at another account — this role carries "
                "every capability, and moving it silently is not something a restart "
                "should be able to do"
            )

    # -- sign-in -------------------------------------------------------

    def sign_in_with_provider(self, identity: OAuthIdentity) -> tuple[User, bool]:
        """Find or create the account for a provider identity.

        Returns ``(user, created)``. A returning member keeps their
        nickname and only has their profile refreshed; the display name
        and avatar are the provider's to change, the nickname is not.
        """
        if not identity.account_id:
            raise NicknameError(
                f"{identity.provider.value} did not return an account id; cannot sign in"
            )
        existing = self._users.find_oauth(identity.provider, identity.account_id)
        if existing is not None:
            user = self._users.update_profile(
                existing.user_id,
                # Never overwrite a stored email with an empty one: an
                # unverified address this time does not erase a verified
                # address from last time.
                email=identity.email or None,
                display_name=identity.display_name or None,
                avatar_url=identity.avatar_url or None,
            )
            self._users.link_oauth(
                user_id=user.id,
                provider=identity.provider,
                provider_account_id=identity.account_id,
                provider_email=identity.email,
            )
            return self.apply_role_policy(user), False

        user = self._users.create(
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
        )
        self._users.link_oauth(
            user_id=user.id,
            provider=identity.provider,
            provider_account_id=identity.account_id,
            provider_email=identity.email,
        )
        logger.info(
            "created account from provider sign-in",
            extra={"context": {"user_id": user.id, "provider": identity.provider.value}},
        )
        return self.apply_role_policy(user), True

    def link_provider(self, user: User, identity: OAuthIdentity) -> OAuthAccount:
        """Attach a second provider to the signed-in account."""
        if not identity.account_id:
            raise NicknameError(
                f"{identity.provider.value} did not return an account id; cannot link"
            )
        owner = self._users.find_oauth(identity.provider, identity.account_id)
        if owner is not None and owner.user_id != user.id:
            # Deliberately not offered as "merge instead?": merging two
            # histories is not reversible and is not this flow's job.
            raise AccountLinkError(
                f"that {identity.provider.value} account is already linked to another "
                "PlanBench account; sign in with it instead"
            )
        account = self._users.link_oauth(
            user_id=user.id,
            provider=identity.provider,
            provider_account_id=identity.account_id,
            provider_email=identity.email,
        )
        # Fill in what the account is still missing, without overwriting
        # anything the member already has.
        self._users.update_profile(
            user.id,
            email=identity.email if (identity.email and not user.email) else None,
            display_name=(
                identity.display_name if (identity.display_name and not user.display_name) else None
            ),
            avatar_url=identity.avatar_url
            if (identity.avatar_url and not user.avatar_url)
            else None,
        )
        return account

    # -- profile -------------------------------------------------------

    def choose_nickname(self, user: User, nickname: str) -> User:
        """Set or change the nickname; uniqueness is case-insensitive."""
        return self.apply_role_policy(
            self._users.set_nickname(user.id, validate_nickname(nickname))
        )

    def nickname_available(self, nickname: str) -> bool:
        """Whether the nickname is free. Raises on an invalid one."""
        validate_nickname(nickname)
        return self._users.find_by_nickname(nickname) is None

    def search(self, prefix: str, limit: int = 10) -> list[User]:
        return [user for user in self._users.search_by_nickname(prefix, limit) if user.nickname]

    def require_by_nickname(self, nickname: str) -> User:
        user = self._users.find_by_nickname(nickname)
        if user is None:
            # Names the nickname on purpose: the member typed it, and
            # "no such member" is the whole point of the message.
            raise NicknameError(f"no member with the nickname {nickname!r}")
        return user

    def get(self, user_id: str) -> User:
        return self._users.get(user_id)

    def providers(self, user_id: str) -> list[AuthProvider]:
        return [account.provider for account in self._users.list_oauth(user_id)]


__all__ = ["AccountService"]
