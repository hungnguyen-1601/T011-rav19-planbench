"""Capability packages, deployment profiles, and the two invariants.

These pin decisions rather than shapes. The one thing worth stating up
front, because it is the reason several assertions look indirect:
**nothing here should have to be edited when a capability is added.**
A test that lists the capabilities of a role is a second copy of the
table, and a second copy is what the whole design is trying not to have.
So the assertions compare the table against itself (the union property),
against the deployment profile that reads it, or against behaviour.
"""

from __future__ import annotations

import pytest

from planbench_api.accounts import (
    ALL_CAPABILITIES,
    BUSINESS_ROLES,
    CAPABILITIES,
    Capability,
    LastAdministratorError,
    Role,
    User,
    capabilities_of,
)
from planbench_api.auth import _parse_seed_entry
from planbench_api.deployment import (
    DeploymentError,
    DeploymentPolicy,
    DeploymentProfile,
    SeparationOfDuties,
    guard_stored_state,
    load_policy,
    parse_default_roles,
    parse_profile,
    parse_seed_roles,
    parse_separation_of_duties,
)
from planbench_api.user_store import InMemoryUserRepository


class TestTheCapabilityTable:
    def test_the_three_packages_cover_every_capability_exactly_once_between_them(self) -> None:
        """A capability nobody filed into a package belongs to nobody.

        This is the test that makes the table maintain itself. Add a
        capability to the enum and forget to put it in a role, and the
        suite says so here — rather than the route quietly admitting
        nobody, which reads as a permissions bug months later.
        """
        union = set().union(*(CAPABILITIES[role] for role in BUSINESS_ROLES))
        assert union == set(ALL_CAPABILITIES), (
            "every capability must belong to at least one business package"
        )

    def test_demo_owner_holds_exactly_what_the_three_packages_hold(self) -> None:
        """Spelled out rather than wildcarded, and checked for drift.

        A ``"*"`` would hand this role any capability added later,
        including one whose author never considered a single account
        holding it beside everything else.
        """
        assert CAPABILITIES[Role.DEMO_OWNER] == ALL_CAPABILITIES

    def test_the_packages_do_not_nest(self) -> None:
        """The property the whole model rests on.

        If reviewer were engineer-plus-extras, "admin" would drift into
        meaning "everything", and the separation this contract exists to
        create would be a naming convention.
        """
        engineer = CAPABILITIES[Role.ENGINEER]
        reviewer = CAPABILITIES[Role.REVIEWER]
        admin = CAPABILITIES[Role.ADMIN]
        assert not engineer <= reviewer and not reviewer <= engineer
        assert not admin <= reviewer and not reviewer <= admin
        assert not admin <= engineer and not engineer <= admin

    def test_an_administrator_holds_no_business_capability(self) -> None:
        """Operating the deployment is not the same job as deciding.

        Named individually because these four are the whole point: an
        account that rotates an API key must not be able to approve a
        run, publish an algorithm, or start work.
        """
        admin = CAPABILITIES[Role.ADMIN]
        assert Capability.RUN_CREATE not in admin
        assert Capability.RUN_REVIEW not in admin
        assert Capability.ALGORITHM_PUBLISH not in admin
        assert Capability.RESOURCE_WRITE not in admin

    def test_holding_two_roles_grants_the_union(self) -> None:
        both = capabilities_of(frozenset({Role.ADMIN, Role.REVIEWER}))
        assert Capability.USER_MANAGE in both
        assert Capability.ALGORITHM_PUBLISH in both

    def test_an_account_with_no_role_can_do_nothing(self) -> None:
        assert User(id="u1").capabilities == frozenset()


class TestDeploymentProfile:
    def test_an_absent_profile_reads_as_production(self) -> None:
        """Fail closed: a server running today has no such variable.

        The desktop launcher does not depend on this default — it sets
        its profile in-process — so the only thing silence can mean here
        is a shared deployment that has not been told otherwise.
        """
        assert parse_profile("") is DeploymentProfile.PRODUCTION

    def test_a_misspelled_profile_is_refused_rather_than_guessed(self) -> None:
        with pytest.raises(DeploymentError, match="not a deployment profile"):
            parse_profile("desktop")

    def test_relaxed_duties_are_refused_on_a_shared_deployment(self) -> None:
        """The combination that would lie about every future approval."""
        with pytest.raises(DeploymentError, match="single-person"):
            parse_separation_of_duties("relaxed", DeploymentProfile.PRODUCTION)

    @pytest.mark.parametrize(
        "profile", [DeploymentProfile.DESKTOP_SINGLE_USER, DeploymentProfile.DEMO]
    )
    def test_relaxed_duties_are_allowed_on_a_single_person_deployment(self, profile) -> None:
        assert parse_separation_of_duties("relaxed", profile) is SeparationOfDuties.RELAXED

    def test_default_roles_may_not_hand_out_reviewer_or_admin(self) -> None:
        """A sign-up form that grants a reviewer grants the signatures."""
        assert parse_default_roles("engineer") == frozenset({Role.ENGINEER})
        assert parse_default_roles("") == frozenset()
        for name in ("reviewer", "admin", "demo_owner"):
            with pytest.raises(DeploymentError):
                parse_default_roles(name)


class TestSeedEntries:
    def test_the_three_part_form_carries_roles(self) -> None:
        assert _parse_seed_entry("admin:engineer+reviewer+admin:secret") == (
            "admin",
            "engineer+reviewer+admin",
            "secret",
        )

    def test_the_two_part_form_still_parses(self) -> None:
        """Installed copies carry the old spelling; it has to keep working."""
        assert _parse_seed_entry("admin:secret") == ("admin", "", "secret")

    def test_a_password_containing_a_colon_survives(self) -> None:
        assert _parse_seed_entry("admin:engineer:a:b") == ("admin", "engineer", "a:b")

    def test_seed_roles_are_ignored_on_a_shared_deployment(self) -> None:
        """A reviewer grown out of an environment variable grew silently."""
        assert parse_seed_roles("engineer+reviewer", DeploymentProfile.PRODUCTION) == frozenset()

    def test_seed_roles_are_honoured_on_a_single_person_deployment(self) -> None:
        assert parse_seed_roles(
            "engineer+reviewer+admin", DeploymentProfile.DESKTOP_SINGLE_USER
        ) == frozenset({Role.ENGINEER, Role.REVIEWER, Role.ADMIN})

    def test_a_seed_entry_can_never_name_the_demo_owner(self) -> None:
        """That role is bound by identity, not by a line carrying a password."""
        assert parse_seed_roles("demo_owner", DeploymentProfile.DEMO) == frozenset()

    def test_an_unknown_role_in_a_seed_entry_is_skipped_not_fatal(self) -> None:
        """A typo must not stop the API booting; sign-in is unaffected."""
        assert parse_seed_roles(
            "engineer+enginer", DeploymentProfile.DESKTOP_SINGLE_USER
        ) == frozenset({Role.ENGINEER})


class TestTheDemoOwnerGuard:
    def _policy(self, profile: DeploymentProfile) -> DeploymentPolicy:
        return DeploymentPolicy(
            profile=profile,
            separation_of_duties=SeparationOfDuties.STRICT,
            default_roles=frozenset({Role.ENGINEER}),
        )

    def test_production_refuses_to_start_while_a_demo_owner_is_assigned(self) -> None:
        """Checked against storage, because that is where it survives.

        The dangerous case is exactly the one where the ``.env`` was
        cleaned up and the grant was not: configuration reads
        ``production`` and one account still holds every capability.
        """
        users = InMemoryUserRepository()
        owner = users.create(nickname="demo-owner", roles={Role.DEMO_OWNER})
        with pytest.raises(DeploymentError) as refusal:
            guard_stored_state(self._policy(DeploymentProfile.PRODUCTION), users)
        message = str(refusal.value)
        assert "demo owner role is still assigned" in message
        # Names the account, because "some account holds it" leaves the
        # operator hunting through a table at the moment they are least
        # able to: the deployment will not start.
        assert owner.nickname in message
        assert "docs/reference/DEMO-PROFILE.md" in message

    def test_a_demo_deployment_starts_with_its_demo_owner(self) -> None:
        users = InMemoryUserRepository()
        users.create(nickname="demo-owner", roles={Role.DEMO_OWNER})
        guard_stored_state(self._policy(DeploymentProfile.DEMO), users)

    def test_production_starts_when_nobody_holds_it(self) -> None:
        users = InMemoryUserRepository()
        users.create(nickname="alice", roles={Role.ENGINEER, Role.ADMIN})
        guard_stored_state(self._policy(DeploymentProfile.PRODUCTION), users)

    def test_demo_owner_settings_are_refused_outside_the_demo_profile(self) -> None:
        class _Settings:
            deployment_profile = "production"
            separation_of_duties = "strict"
            default_roles = "engineer"
            demo_owner_email = "someone@example.com"
            demo_owner_nickname = ""

        with pytest.raises(DeploymentError, match="only under the 'demo' profile"):
            load_policy(_Settings())


class TestTheAdministratorInvariant:
    """Somebody must always be able to manage accounts.

    Counted by **capability**, not by the ``admin`` role. Counting the
    name is wrong in both directions once ``demo_owner`` exists: it lets
    the last real administrator go while a demo account holds the keys,
    and it blocks removing a demo account that a freshly granted
    administrator has already replaced.
    """

    def test_the_last_account_that_can_manage_users_cannot_be_demoted(self) -> None:
        users = InMemoryUserRepository()
        only = users.create(nickname="root", roles={Role.ADMIN})
        with pytest.raises(LastAdministratorError):
            users.set_roles(only.id, frozenset({Role.ENGINEER}))
        assert Role.ADMIN in users.get(only.id).roles, "the refusal must leave the grant intact"

    def test_the_last_account_that_can_manage_users_cannot_be_disabled(self) -> None:
        """Disabling is a role change in everything but name."""
        users = InMemoryUserRepository()
        only = users.create(nickname="root", roles={Role.ADMIN})
        with pytest.raises(LastAdministratorError):
            users.set_disabled(only.id, True)
        assert not users.get(only.id).disabled

    def test_a_demo_owner_counts_as_an_administrator(self) -> None:
        """Because they hold ``user.manage`` — the capability is the test."""
        users = InMemoryUserRepository()
        admin = users.create(nickname="root", roles={Role.ADMIN})
        users.create(nickname="demo", roles={Role.DEMO_OWNER})
        users.set_roles(admin.id, frozenset({Role.ENGINEER}))
        assert users.get(admin.id).roles == frozenset({Role.ENGINEER})

    def test_demotion_is_allowed_once_somebody_else_can_manage_users(self) -> None:
        users = InMemoryUserRepository()
        first = users.create(nickname="root", roles={Role.ADMIN})
        users.create(nickname="second", roles={Role.ADMIN})
        users.set_roles(first.id, frozenset({Role.ENGINEER}))
        assert users.get(first.id).roles == frozenset({Role.ENGINEER})

    def test_a_disabled_administrator_does_not_count(self) -> None:
        """An account that cannot sign in cannot administer anything."""
        users = InMemoryUserRepository()
        active = users.create(nickname="root", roles={Role.ADMIN})
        asleep = users.create(nickname="other", roles={Role.ADMIN})
        users.set_disabled(asleep.id, True)
        with pytest.raises(LastAdministratorError):
            users.set_roles(active.id, frozenset({Role.ENGINEER}))


@pytest.fixture
def sql_users(tmp_path):
    """The SQL user repository, on a throwaway SQLite file.

    Worth its own fixture because the invariant is implemented twice —
    once with a lock, once with a transaction — and only one of them is
    the one production runs.
    """
    from planbench_api.artifacts import FileSystemArtifactStore
    from planbench_api.db import SessionFactory, create_all, create_db_engine
    from planbench_api.db.repositories import SqlRepositoryHub

    engine = create_db_engine(f"sqlite:///{tmp_path / 'roles.db'}")
    create_all(engine)
    sessions = SessionFactory(engine)
    hub = SqlRepositoryHub(sessions, FileSystemArtifactStore(str(tmp_path / "artifacts")))
    yield hub.users
    sessions.dispose()


class TestTheSameRulesOverSql:
    """The storage the deployment actually runs must agree with the model.

    Repeated rather than shared, because the two backends implement the
    invariant by different means: the in-memory one holds a lock and
    rolls back by hand, the SQL one checks inside the transaction. A
    guarantee that holds in only one of them is not a guarantee.
    """

    def test_roles_survive_a_round_trip(self, sql_users) -> None:
        user = sql_users.create(nickname="alice", roles={Role.ENGINEER, Role.REVIEWER})
        assert sql_users.get(user.id).roles == frozenset({Role.ENGINEER, Role.REVIEWER})

    def test_is_admin_is_derived_from_the_roles_not_from_the_old_column(self, sql_users) -> None:
        """The column is dead; nothing may resurrect it as a second answer."""
        plain = sql_users.create(nickname="plain", roles={Role.ENGINEER})
        assert plain.is_admin is False
        sql_users.create(nickname="root", roles={Role.ADMIN})
        promoted = sql_users.set_roles(plain.id, frozenset({Role.ENGINEER, Role.ADMIN}))
        assert promoted.is_admin is True

    def test_the_last_account_that_can_manage_users_cannot_be_demoted(self, sql_users) -> None:
        only = sql_users.create(nickname="root", roles={Role.ADMIN})
        with pytest.raises(LastAdministratorError):
            sql_users.set_roles(only.id, frozenset({Role.ENGINEER}))
        assert Role.ADMIN in sql_users.get(only.id).roles

    def test_the_last_account_that_can_manage_users_cannot_be_disabled(self, sql_users) -> None:
        only = sql_users.create(nickname="root", roles={Role.ADMIN})
        with pytest.raises(LastAdministratorError):
            sql_users.set_disabled(only.id, True)
        assert not sql_users.get(only.id).disabled

    def test_a_second_demo_owner_is_refused_by_the_database(self, sql_users) -> None:
        """The unique index, not the service check.

        The service check gives a readable message and loses a race; this
        is the one that cannot be raced, and it is the reason a role
        carrying every capability is safe to have at all.
        """
        from sqlalchemy.exc import IntegrityError

        sql_users.create(nickname="root", roles={Role.ADMIN})
        sql_users.create(nickname="demo", roles={Role.DEMO_OWNER})
        second = sql_users.create(nickname="other", roles={Role.ENGINEER})
        with pytest.raises(IntegrityError):
            sql_users.set_roles(second.id, frozenset({Role.DEMO_OWNER}))

    def test_an_unknown_role_in_storage_does_not_make_the_account_unloadable(
        self, sql_users, tmp_path
    ) -> None:
        """Losing one capability is recoverable; a sign-in that raises is not."""
        import sqlalchemy as sa

        from planbench_api.db import create_db_engine

        user = sql_users.create(nickname="alice", roles={Role.ENGINEER})
        engine = create_db_engine(f"sqlite:///{tmp_path / 'roles.db'}")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO user_roles (user_id, role, reason, granted_at) "
                    "VALUES (:id, 'archaeologist', '', '2026-01-01T00:00:00+00:00')"
                ),
                {"id": user.id},
            )
        engine.dispose()
        assert sql_users.get(user.id).roles == frozenset({Role.ENGINEER})


class TestSeedReconciliation:
    """What carries an installed copy across an upgrade.

    A desktop install created its account before roles existed. Nothing
    else would ever grant them, so without this the account somebody
    signs in with every day comes back from the update holding nothing —
    on a machine being used to evaluate the product.
    """

    def _service(self, tmp_path, monkeypatch, users, *, seed: str, profile: str):
        import os

        from planbench_api.auth import AuthService
        from planbench_api.config import Settings, get_settings

        # Cleared rather than assumed: a developer machine with
        # PLANBENCH_ADMIN_NICKNAMES set would hand every account here an
        # admin role and the reconciliation assertions would pass for the
        # wrong reason.
        for name in list(os.environ):
            if name.startswith("PLANBENCH_"):
                monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("PLANBENCH_ENABLE_DEV_LOGIN", "true")
        monkeypatch.setenv("PLANBENCH_SEED_USERS", seed)
        monkeypatch.setenv("PLANBENCH_DEPLOYMENT_PROFILE", profile)
        get_settings.cache_clear()
        service = AuthService(Settings(), users)
        get_settings.cache_clear()
        return service

    def test_a_desktop_account_created_before_roles_gains_them_on_boot(
        self, tmp_path, monkeypatch
    ) -> None:
        users = InMemoryUserRepository()
        from planbench_api.auth import hash_password

        legacy = users.create(nickname="admin", password_hash=hash_password("admin"))
        assert legacy.roles == frozenset(), "the account this simulates predates roles"

        self._service(
            tmp_path,
            monkeypatch,
            users,
            seed="admin:engineer+reviewer+admin:admin",
            profile="desktop-single-user",
        )
        assert users.get(legacy.id).roles == frozenset({Role.ENGINEER, Role.REVIEWER, Role.ADMIN})

    def test_reconciliation_adds_and_never_removes(self, tmp_path, monkeypatch) -> None:
        """Configuration is a floor, not a ceiling.

        Otherwise a role an administrator granted through the UI would be
        revoked by the next restart, and the restart would win by being
        the thing that runs last.
        """
        from planbench_api.auth import hash_password

        users = InMemoryUserRepository()
        granted = users.create(
            nickname="admin",
            roles={Role.ADMIN, Role.REVIEWER},
            password_hash=hash_password("admin"),
        )
        self._service(
            tmp_path, monkeypatch, users, seed="admin:engineer:admin", profile="desktop-single-user"
        )
        assert users.get(granted.id).roles == frozenset({Role.ENGINEER, Role.REVIEWER, Role.ADMIN})

    def test_a_shared_deployment_does_not_reconcile_seed_roles(self, tmp_path, monkeypatch) -> None:
        from planbench_api.auth import hash_password

        users = InMemoryUserRepository()
        existing = users.create(nickname="admin", password_hash=hash_password("admin"))
        self._service(
            tmp_path,
            monkeypatch,
            users,
            seed="admin:engineer+reviewer:admin",
            profile="production",
        )
        assert users.get(existing.id).roles == frozenset()

    def test_a_new_desktop_account_is_created_holding_its_roles(
        self, tmp_path, monkeypatch
    ) -> None:
        users = InMemoryUserRepository()
        self._service(
            tmp_path,
            monkeypatch,
            users,
            seed="engineer:engineer:engineer,reviewer:reviewer:reviewer",
            profile="desktop-single-user",
        )
        assert users.find_by_nickname("engineer").roles == frozenset({Role.ENGINEER})
        assert users.find_by_nickname("reviewer").roles == frozenset({Role.REVIEWER})
