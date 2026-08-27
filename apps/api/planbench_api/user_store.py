"""In-memory user, OAuth-account and review-request repositories.

The counterpart of :mod:`planbench_api.repositories` for identity. They
exist for the same reason: a checkout with no database still runs the
whole API and the whole test suite. The SQL implementations in
:mod:`planbench_api.db.repositories` satisfy the same ports and return
the same objects.

Nickname uniqueness is enforced on the case-folded key, not the display
form, so ``Alice`` and ``alice`` cannot both exist — otherwise "send a
review to alice" would be ambiguous in exactly the situation where being
unambiguous matters.
"""

from __future__ import annotations

import threading
import uuid

from planbench_api.accounts import (
    AccountEvent,
    AccountLinkError,
    AuthProvider,
    Capability,
    LastAdministratorError,
    NicknameError,
    OAuthAccount,
    Role,
    StoredUser,
    User,
    normalise_nickname,
    now_iso,
    validate_nickname,
)
from planbench_api.errors import NotFoundError
from planbench_api.review import ReviewRequest, ReviewStatus


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, StoredUser] = {}
        self._by_nickname: dict[str, str] = {}
        self._oauth: dict[str, OAuthAccount] = {}
        self._account_events: list[AccountEvent] = []
        self._lock = threading.RLock()

    # -- users ---------------------------------------------------------

    def create(
        self,
        *,
        nickname: str = "",
        email: str = "",
        display_name: str = "",
        avatar_url: str = "",
        roles: frozenset[Role] | set[Role] = frozenset(),
        password_hash: str | None = None,
    ) -> User:
        with self._lock:
            key = ""
            if nickname:
                nickname = validate_nickname(nickname)
                key = normalise_nickname(nickname)
                if key in self._by_nickname:
                    raise NicknameError(f"nickname {nickname!r} is already taken")
            stamp = now_iso()
            user = User(
                id=new_id(),
                nickname=nickname,
                email=email,
                display_name=display_name,
                avatar_url=avatar_url,
                roles=frozenset(roles),
                created_at=stamp,
                updated_at=stamp,
            )
            self._users[user.id] = StoredUser(
                user=user, nickname_key=key, password_hash=password_hash
            )
            if key:
                self._by_nickname[key] = user.id
            return user

    def get(self, user_id: str) -> User:
        stored = self._users.get(user_id)
        if stored is None:
            raise NotFoundError("user", user_id)
        return stored.user

    def get_stored(self, user_id: str) -> StoredUser:
        stored = self._users.get(user_id)
        if stored is None:
            raise NotFoundError("user", user_id)
        return stored

    def find_by_nickname(self, nickname: str) -> User | None:
        user_id = self._by_nickname.get(normalise_nickname(nickname))
        return self._users[user_id].user if user_id else None

    def search_by_nickname(self, prefix: str, limit: int = 10) -> list[User]:
        needle = normalise_nickname(prefix)
        if not needle:
            return []
        matches = [
            stored.user for stored in self._users.values() if stored.nickname_key.startswith(needle)
        ]
        matches.sort(key=lambda user: user.nickname.casefold())
        return matches[:limit]

    def set_nickname(self, user_id: str, nickname: str) -> User:
        with self._lock:
            stored = self.get_stored(user_id)
            cleaned = validate_nickname(nickname)
            key = normalise_nickname(cleaned)
            owner = self._by_nickname.get(key)
            if owner is not None and owner != user_id:
                raise NicknameError(f"nickname {cleaned!r} is already taken")
            if stored.nickname_key:
                self._by_nickname.pop(stored.nickname_key, None)
            user = stored.user.model_copy(update={"nickname": cleaned, "updated_at": now_iso()})
            self._users[user_id] = stored.model_copy(update={"user": user, "nickname_key": key})
            self._by_nickname[key] = user_id
            return user

    def update_profile(
        self,
        user_id: str,
        *,
        email: str | None = None,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        with self._lock:
            stored = self.get_stored(user_id)
            updates = {"updated_at": now_iso()}
            if email is not None:
                updates["email"] = email
            if display_name is not None:
                updates["display_name"] = display_name
            if avatar_url is not None:
                updates["avatar_url"] = avatar_url
            user = stored.user.model_copy(update=updates)
            self._users[user_id] = stored.model_copy(update={"user": user})
            return user

    def set_roles(
        self,
        user_id: str,
        roles: frozenset[Role] | set[Role],
        *,
        granted_by_user_id: str | None = None,
        reason: str = "",
    ) -> User:
        """Replace the role set, under the same administrator invariant.

        The lock plays the part the SQL transaction plays: the check runs
        after the change is applied and rolls it back on refusal, so two
        concurrent revocations cannot each see the other's administrator
        still standing.
        """
        with self._lock:
            stored = self.get_stored(user_id)
            previous = stored.user
            user = previous.model_copy(update={"roles": frozenset(roles), "updated_at": now_iso()})
            self._users[user_id] = stored.model_copy(update={"user": user})
            try:
                self._require_a_remaining_administrator()
            except LastAdministratorError:
                self._users[user_id] = stored.model_copy(update={"user": previous})
                raise
            return user

    def set_disabled(self, user_id: str, disabled: bool) -> User:
        with self._lock:
            stored = self.get_stored(user_id)
            previous = stored.user
            user = previous.model_copy(
                update={"disabled_at": now_iso() if disabled else "", "updated_at": now_iso()}
            )
            self._users[user_id] = stored.model_copy(update={"user": user})
            try:
                self._require_a_remaining_administrator()
            except LastAdministratorError:
                self._users[user_id] = stored.model_copy(update={"user": previous})
                raise
            return user

    def record_sign_in(self, user_id: str) -> None:
        with self._lock:
            stored = self.get_stored(user_id)
            user = stored.user.model_copy(update={"updated_at": now_iso()})
            self._users[user_id] = stored.model_copy(update={"user": user})

    def list_with_role(self, role: Role) -> list[User]:
        with self._lock:
            return [stored.user for stored in self._users.values() if role in stored.user.roles]

    def record_account_event(self, event: AccountEvent) -> AccountEvent:
        with self._lock:
            stamped = event.model_copy(
                update={
                    "sequence": len(self._account_events) + 1,
                    "created_at": event.created_at or now_iso(),
                }
            )
            self._account_events.append(stamped)
            return stamped

    def list_account_events(self, user_id: str | None = None) -> list[AccountEvent]:
        with self._lock:
            if user_id is None:
                return list(self._account_events)
            return [event for event in self._account_events if event.user_id == user_id]

    def _require_a_remaining_administrator(self) -> None:
        for stored in self._users.values():
            if stored.user.disabled:
                continue
            if Capability.USER_MANAGE in stored.user.capabilities:
                return
        raise LastAdministratorError(
            "this would leave the deployment with no enabled account able to manage "
            "users. Grant another account an administering role first"
        )

    def set_password(self, user_id: str, password_hash: str) -> User:
        """Replace the credential an account signs in with."""
        with self._lock:
            stored = self.get_stored(user_id)
            user = stored.user.model_copy(update={"updated_at": now_iso()})
            self._users[user_id] = stored.model_copy(
                update={"user": user, "password_hash": password_hash}
            )
            return user

    def list(self) -> list[User]:
        return sorted(
            (stored.user for stored in self._users.values()), key=lambda user: user.created_at
        )

    # -- OAuth accounts ------------------------------------------------

    def link_oauth(
        self,
        *,
        user_id: str,
        provider: AuthProvider,
        provider_account_id: str,
        provider_email: str = "",
    ) -> OAuthAccount:
        with self._lock:
            self.get(user_id)  # 404 if the account vanished
            existing = self.find_oauth(provider, provider_account_id)
            if existing is not None and existing.user_id != user_id:
                raise AccountLinkError(
                    f"that {provider.value} account is already linked to another PlanBench account"
                )
            stamp = now_iso()
            if existing is not None:
                updated = existing.model_copy(
                    update={"provider_email": provider_email, "updated_at": stamp}
                )
                self._oauth[updated.id] = updated
                return updated
            account = OAuthAccount(
                id=new_id(),
                user_id=user_id,
                provider=provider,
                provider_account_id=provider_account_id,
                provider_email=provider_email,
                created_at=stamp,
                updated_at=stamp,
            )
            self._oauth[account.id] = account
            return account

    def find_oauth(self, provider: AuthProvider, provider_account_id: str) -> OAuthAccount | None:
        for account in self._oauth.values():
            if account.provider is provider and account.provider_account_id == provider_account_id:
                return account
        return None

    def list_oauth(self, user_id: str) -> list[OAuthAccount]:
        return sorted(
            (account for account in self._oauth.values() if account.user_id == user_id),
            key=lambda account: account.created_at,
        )


class InMemoryReviewRepository:
    def __init__(self) -> None:
        self._items: dict[str, ReviewRequest] = {}
        self._lock = threading.RLock()

    def create(self, request: ReviewRequest) -> ReviewRequest:
        with self._lock:
            stored = request.model_copy(update={"id": request.id or new_id()})
            if not stored.created_at:
                stored = stored.model_copy(update={"created_at": now_iso()})
            self._items[stored.id] = stored
            return stored

    def get(self, request_id: str) -> ReviewRequest:
        request = self._items.get(request_id)
        if request is None:
            raise NotFoundError("review request", request_id)
        return request

    def save(self, request: ReviewRequest) -> ReviewRequest:
        with self._lock:
            self._items[request.id] = request
            return request

    def list_for_benchmark(self, benchmark_id: str) -> list[ReviewRequest]:
        return self._sorted(
            request for request in self._items.values() if request.benchmark_id == benchmark_id
        )

    def list_for_reviewer(
        self, reviewer_user_id: str, status: ReviewStatus | None = None
    ) -> list[ReviewRequest]:
        return self._sorted(
            request
            for request in self._items.values()
            if request.reviewer_user_id == reviewer_user_id
            and (status is None or request.status is status)
        )

    def list_requested_by(self, user_id: str) -> list[ReviewRequest]:
        return self._sorted(
            request for request in self._items.values() if request.requested_by_user_id == user_id
        )

    @staticmethod
    def _sorted(requests) -> list[ReviewRequest]:
        # Newest first: an inbox is read from the top.
        return sorted(requests, key=lambda request: request.created_at, reverse=True)


__all__ = ["InMemoryReviewRepository", "InMemoryUserRepository", "new_id"]
