"""An installed copy upgrading onto this code keeps its access.

This is the test that stands between the branch and a broken release.
People are using the shipped desktop build to evaluate the product, and
they sign in as ``admin``. Their machine holds an ``.env`` written by a
version that predates roles: a two-part seed line, no deployment
profile, no duties setting.

Two ways that goes wrong, and both were measured before this existed:

* the server reads a missing profile as ``production`` — correct for a
  server — and the account comes back holding engineer and admin, unable
  to approve a configuration or import an algorithm;
* setting the profile alone fixes nothing, because the old seed line
  names no roles, so a reconciliation has nothing to reconcile.

So the launcher supplies both, on every launch, and this asserts the
outcome rather than the mechanism: sign in, and be able to do the work.
"""

from __future__ import annotations

import pytest

from planbench_desktop.provision import (
    DEFAULT_NICKNAME,
    PROFILE_DEFAULTS,
    apply_profile_defaults,
    seed_users_line,
)

#: Exactly what a 0.1.14 install wrote.
OLD_ENV = """\
AUTH_SECRET=an-old-secret-value
PLANBENCH_ENABLE_DEV_LOGIN=true
PLANBENCH_SEED_USERS=admin:admin
PLANBENCH_ADMIN_NICKNAMES=admin
PLANBENCH_DATABASE_URL=sqlite:///planbench.db
"""


@pytest.fixture
def old_install(tmp_path, monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith("PLANBENCH_"):
            monkeypatch.delenv(name, raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(OLD_ENV, encoding="utf-8")
    return env_path


class TestWhatTheLauncherSupplies:
    def test_it_states_the_profile_the_file_never_mentioned(self, old_install) -> None:
        import os

        applied = apply_profile_defaults(old_install)
        assert applied["PLANBENCH_DEPLOYMENT_PROFILE"] == "desktop-single-user"
        assert os.environ["PLANBENCH_DEPLOYMENT_PROFILE"] == "desktop-single-user"

    def test_it_fills_in_the_roles_the_old_seed_line_omits(self, old_install) -> None:
        """The half that setting the profile alone does not fix.

        A two-part entry names a password and nothing else, so the boot
        reconciliation finds no roles to grant and the account stays
        exactly as under-privileged as it was.
        """
        applied = apply_profile_defaults(old_install)
        line = applied["PLANBENCH_SEED_USERS"]
        assert "engineer+reviewer+admin" in line
        assert line.startswith("admin:")

    def test_it_keeps_the_password_that_was_already_there(self, old_install) -> None:
        """Changing somebody's credential is not a thing an upgrade may do."""
        old_install.write_text(
            OLD_ENV.replace(
                "PLANBENCH_SEED_USERS=admin:admin", "PLANBENCH_SEED_USERS=admin:hunter2"
            ),
            encoding="utf-8",
        )
        line = apply_profile_defaults(old_install)["PLANBENCH_SEED_USERS"]
        assert line.split(",")[0].endswith(":hunter2")

    def test_a_renamed_account_keeps_its_name_and_gains_the_roles(self, old_install) -> None:
        """Inventing accounts on somebody's machine is not repair.

        They renamed theirs; grant the three packages to the name they
        actually use and leave the stock two out.
        """
        old_install.write_text(
            OLD_ENV.replace("PLANBENCH_SEED_USERS=admin:admin", "PLANBENCH_SEED_USERS=an:secret"),
            encoding="utf-8",
        )
        line = apply_profile_defaults(old_install)["PLANBENCH_SEED_USERS"]
        assert line == "an:engineer+reviewer+admin:secret"

    def test_relaxed_duties_because_one_person_cannot_be_two(self, old_install) -> None:
        applied = apply_profile_defaults(old_install)
        assert applied["PLANBENCH_SEPARATION_OF_DUTIES"] == "relaxed"


class TestWhatTheFileSaysWins:
    def test_an_explicit_profile_is_left_alone(self, old_install) -> None:
        """Somebody who set this meant it — the demo profile, for instance."""
        old_install.write_text(OLD_ENV + "PLANBENCH_DEPLOYMENT_PROFILE=demo\n", encoding="utf-8")
        applied = apply_profile_defaults(old_install)
        assert "PLANBENCH_DEPLOYMENT_PROFILE" not in applied

    def test_a_seed_line_that_already_names_roles_is_left_alone(self, old_install) -> None:
        old_install.write_text(
            OLD_ENV.replace(
                "PLANBENCH_SEED_USERS=admin:admin",
                "PLANBENCH_SEED_USERS=admin:engineer:admin",
            ),
            encoding="utf-8",
        )
        applied = apply_profile_defaults(old_install)
        assert "PLANBENCH_SEED_USERS" not in applied

    def test_a_current_install_needs_nothing(self, tmp_path, monkeypatch) -> None:
        """A file written by this version already says all of it."""
        import os

        for name in list(os.environ):
            if name.startswith("PLANBENCH_"):
                monkeypatch.delenv(name, raising=False)
        env_path = tmp_path / ".env"
        env_path.write_text(
            f"PLANBENCH_SEED_USERS={seed_users_line('admin')}\n"
            + "".join(f"{name}={value}\n" for name, value in PROFILE_DEFAULTS.items()),
            encoding="utf-8",
        )
        assert apply_profile_defaults(env_path) == {}


class TestTheAccountCanActuallyDoTheWork:
    """The outcome, not the mechanism.

    Boots the API against a database migrated from the old schema and
    asks the account what it may do — which is the only form of this
    check that would have caught the second failure above, since that
    one passed every assertion about the profile.
    """

    def test_signing_in_after_an_upgrade_gives_back_the_whole_workflow(
        self, tmp_path, monkeypatch, old_install
    ) -> None:
        import bcrypt
        import sqlalchemy as sa
        from fastapi.testclient import TestClient

        from planbench_api.config import get_settings
        from planbench_api.db import create_all, create_db_engine
        from planbench_api.main import create_app

        database = tmp_path / "planbench.db"
        engine = create_db_engine(f"sqlite:///{database}")
        create_all(engine)
        # The account as the old build left it: is_admin, no user_roles
        # row, because the table did not exist when it was created.
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO users (id,nickname,nickname_key,email,display_name,"
                    "avatar_url,is_admin,password_hash,created_at,updated_at) VALUES "
                    "('u_admin','admin','admin','','admin','',1,:hash,'t','t')"
                ),
                {"hash": bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()},
            )
        engine.dispose()

        apply_profile_defaults(old_install)
        monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{database}")
        monkeypatch.setenv("PLANBENCH_ENABLE_DEV_LOGIN", "true")
        monkeypatch.setenv("PLANBENCH_ADMIN_NICKNAMES", DEFAULT_NICKNAME)
        monkeypatch.setenv("AUTH_SECRET", "long-enough-secret-for-the-probe")
        get_settings.cache_clear()
        app = create_app(artifact_dir=str(tmp_path / "artifacts"))
        try:
            client = TestClient(app, raise_server_exceptions=False)
            login = client.post(
                "/api/v1/auth/login", data={"username": "admin", "password": "admin"}
            )
            assert login.status_code == 200, login.text
            me = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            ).json()
            assert set(me["roles"]) == {"engineer", "reviewer", "admin"}
            capabilities = set(me["capabilities"])
            for capability in (
                "run.create",
                "run.review",
                "algorithm.import",
                "algorithm.publish",
                "user.manage",
                "resource.write",
            ):
                assert capability in capabilities, capability
        finally:
            if app.state.sessions is not None:
                app.state.sessions.dispose()
            get_settings.cache_clear()
