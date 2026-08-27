"""API tests: authentication, and what a token is allowed to be.

The old role tests are gone with the roles. What replaces them is the
property that matters now: a token identifies an account, every signed-in
member can create work, and nothing about a request other than the token
decides who the caller is.
"""

from __future__ import annotations

from conftest import ADMIN, ALICE, BOB, auth_headers, isolate_environment
from fastapi.testclient import TestClient

from planbench_api.config import get_settings
from planbench_api.main import create_app


def benchmark_payload(created_map: dict, created_scenario: dict, name: str = "b") -> dict:
    return {
        "name": name,
        "map_id": created_map["id"],
        "scenario_id": created_scenario["id"],
        "algorithms": [{"id": "astar+dwa"}],
        "seeds": [1],
    }


class TestLogin:
    def test_valid_credentials_return_a_token_and_the_account(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login", data={"username": ALICE[0], "password": ALICE[1]}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["expires_in"] > 0
        assert body["user"]["nickname"] == ALICE[0]
        assert body["user"]["needs_nickname"] is False

    def test_wrong_password_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login", data={"username": ALICE[0], "password": "wrong"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_unknown_user_rejected(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/login", data={"username": "nobody", "password": "x"})
        assert response.status_code == 401

    def test_an_unknown_user_is_indistinguishable_from_a_wrong_password(
        self, client: TestClient
    ) -> None:
        """Otherwise the login form doubles as a member directory."""
        unknown = client.post("/api/v1/auth/login", data={"username": "nobody", "password": "x"})
        wrong = client.post("/api/v1/auth/login", data={"username": ALICE[0], "password": "x"})
        assert unknown.json() == wrong.json()

    def test_me_returns_the_caller(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/me", headers=auth_headers(client, BOB))
        assert response.status_code == 200
        body = response.json()
        assert body["nickname"] == BOB[0]
        assert body["is_admin"] is False
        # No password hash, no token, nothing but the profile — plus what
        # the caller may do, which the interface has to be told rather
        # than work out. Sending roles alone would make the web app keep
        # its own copy of the role→capability table, and a second copy of
        # that table is how a button gets offered to somebody the server
        # then refuses.
        assert set(body) == {
            "id",
            "nickname",
            "email",
            "display_name",
            "avatar_url",
            "roles",
            "capabilities",
            "is_admin",
            "needs_nickname",
            "providers",
        }

    def test_me_reports_capabilities_rather_than_leaving_them_to_be_inferred(
        self, client: TestClient
    ) -> None:
        """A seeded account can act, and the response says how.

        Pinned as a property, not as a list: the point is that the two
        fields agree with the server's own table, so moving a capability
        between packages keeps this test honest instead of breaking it.
        """
        from planbench_api.accounts import CAPABILITIES, Role

        body = client.get("/api/v1/auth/me", headers=auth_headers(client, BOB)).json()
        roles = {Role(name) for name in body["roles"]}
        assert roles, "a seeded account with no role at all could sign in and do nothing"
        expected = set().union(*(CAPABILITIES[role] for role in roles))
        assert {capability.value for capability in expected} == set(body["capabilities"])


class TestDevLoginFlag:
    """Password sign-in exists only where it was asked for."""

    def test_login_is_refused_when_dev_login_is_off(self, tmp_path, monkeypatch) -> None:
        from conftest import isolate_environment

        isolate_environment(monkeypatch)
        monkeypatch.setenv("PLANBENCH_ENABLE_DEV_LOGIN", "false")
        get_settings.cache_clear()
        client = TestClient(
            create_app(artifact_dir=str(tmp_path / "artifacts")), raise_server_exceptions=False
        )
        response = client.post(
            "/api/v1/auth/login", data={"username": ALICE[0], "password": ALICE[1]}
        )
        get_settings.cache_clear()
        assert response.status_code == 401
        assert "disabled" in response.json()["error"]["message"]

    def test_providers_reports_what_is_actually_available(self, client: TestClient) -> None:
        """With no OAuth configured the site still answers, with no buttons."""
        body = client.get("/api/v1/auth/providers").json()
        assert body == {"google": False, "github": False, "dev_login": True}


class TestAccessControl:
    def test_benchmarks_require_authentication(self, client: TestClient) -> None:
        response = client.get("/api/v1/benchmarks")
        assert response.status_code == 401

    def test_invalid_token_rejected(self, client: TestClient) -> None:
        response = client.get("/api/v1/benchmarks", headers={"Authorization": "Bearer not-a-token"})
        assert response.status_code == 401

    def test_every_member_can_create_a_benchmark(
        self, client: TestClient, created_map: dict, created_scenario: dict, bob_headers
    ) -> None:
        """There is no creator role: being signed in is the whole rule."""
        response = client.post(
            "/api/v1/benchmarks",
            json=benchmark_payload(created_map, created_scenario, "bobs"),
            headers=bob_headers,
        )
        assert response.status_code == 201
        assert response.json()["is_owner"] is True

    def test_admin_is_granted_by_configuration_only(self, client: TestClient) -> None:
        assert client.get("/api/v1/auth/me", headers=auth_headers(client, ADMIN)).json()["is_admin"]
        assert not client.get("/api/v1/auth/me", headers=auth_headers(client, ALICE)).json()[
            "is_admin"
        ]

    def test_a_token_for_a_deleted_account_stops_working(self, client: TestClient, app) -> None:
        """The token is a pointer to an account, not a copy of one."""
        headers = auth_headers(client, ALICE)
        users = app.state.repos.users
        user = users.find_by_nickname(ALICE[0])
        users._users.pop(user.id)  # only the in-memory backend can be poked like this
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401


class TestASeedPasswordThatChanged:
    """`PLANBENCH_SEED_USERS` has to keep meaning something after day one.

    Creating-only meant the setting was read exactly once in an
    installation's life. Change the entry afterwards and the file said
    one password while the database held the hash of another — the
    sign-in page rejecting the credential printed right beside it, with
    nothing in the interface to explain why. A desktop build shipped
    that way.
    """

    @staticmethod
    def _sign_in(client: TestClient, nickname: str, password: str):
        return client.post("/api/v1/auth/login", data={"username": nickname, "password": password})

    def test_the_new_password_works_after_the_entry_changes(self, tmp_path, monkeypatch) -> None:
        isolate_environment(monkeypatch)
        monkeypatch.setenv("PLANBENCH_MODEL_DIR", str(tmp_path / "models"))
        database = tmp_path / "seeded.db"
        monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{database.as_posix()}")
        monkeypatch.setenv("PLANBENCH_DB_CREATE_ALL", "true")

        monkeypatch.setenv("PLANBENCH_SEED_USERS", "admin:the-first-password")
        get_settings.cache_clear()
        first = TestClient(create_app(artifact_dir=str(tmp_path / "a")))
        assert self._sign_in(first, "admin", "the-first-password").status_code == 200

        # Same database, a different entry — the shape of editing `.env`
        # and reopening the app.
        monkeypatch.setenv("PLANBENCH_SEED_USERS", "admin:the-second-password")
        get_settings.cache_clear()
        second = TestClient(create_app(artifact_dir=str(tmp_path / "b")))

        assert self._sign_in(second, "admin", "the-second-password").status_code == 200
        assert self._sign_in(second, "admin", "the-first-password").status_code == 401
        get_settings.cache_clear()

    def test_an_unchanged_entry_leaves_the_account_alone(self, tmp_path, monkeypatch) -> None:
        """Reconciling must not mean rewriting the hash on every boot."""
        isolate_environment(monkeypatch)
        monkeypatch.setenv("PLANBENCH_MODEL_DIR", str(tmp_path / "models"))
        database = tmp_path / "stable.db"
        monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{database.as_posix()}")
        monkeypatch.setenv("PLANBENCH_DB_CREATE_ALL", "true")
        monkeypatch.setenv("PLANBENCH_SEED_USERS", "admin:unchanged")

        get_settings.cache_clear()
        TestClient(create_app(artifact_dir=str(tmp_path / "a")))
        import sqlite3

        with sqlite3.connect(database) as connection:
            before = connection.execute(
                "SELECT password_hash FROM users WHERE nickname = 'admin'"
            ).fetchone()[0]

        get_settings.cache_clear()
        again = TestClient(create_app(artifact_dir=str(tmp_path / "b")))
        with sqlite3.connect(database) as connection:
            after = connection.execute(
                "SELECT password_hash FROM users WHERE nickname = 'admin'"
            ).fetchone()[0]

        assert after == before
        assert self._sign_in(again, "admin", "unchanged").status_code == 200
        get_settings.cache_clear()
