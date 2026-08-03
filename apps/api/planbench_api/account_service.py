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
    AccountLinkError,
    AuthProvider,
    NicknameError,
    OAuthAccount,
    User,
    validate_nickname,
)
from planbench_api.oauth import OAuthIdentity
from planbench_api.repository_ports import UserRepositoryPort

logger = logging.getLogger("planbench.api.accounts")


def _split(value: str) -> frozenset[str]:
    return frozenset(part.strip().casefold() for part in value.split(",") if part.strip())


class AccountService:
    """Accounts, and the one rule about who is an admin.

    Admin comes from configuration — a nickname or a verified email the
    deployment listed — and is re-applied on every sign-in so adding
    somebody to the list takes effect without a database edit. It is
    never inferred from anything a user supplies.
    """

    def __init__(
        self,
        users: UserRepositoryPort,
        admin_nicknames: str = "",
        admin_emails: str = "",
    ) -> None:
        self._users = users
        self._admin_nicknames = _split(admin_nicknames)
        self._admin_emails = _split(admin_emails)

    def apply_admin_policy(self, user: User) -> User:
        """Grant or revoke admin from the configured lists."""
        if not self._admin_nicknames and not self._admin_emails:
            return user
        should_be = (bool(user.nickname) and user.nickname.casefold() in self._admin_nicknames) or (
            bool(user.email) and user.email.casefold() in self._admin_emails
        )
        if should_be == user.is_admin:
            return user
        return self._users.set_admin(user.id, should_be)

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
            return self.apply_admin_policy(user), False

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
        return self.apply_admin_policy(user), True

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
        return self.apply_admin_policy(
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
