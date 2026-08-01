"""Fixtures for API tests: fresh app per test, signed-in clients, resources.

Four accounts. ``alice`` is an Engineer — she creates benchmarks and
owns them. ``bob`` and ``carol`` are Approvers, because the existing
suite already uses both interchangeably as "the reviewer" and "a third
member who is not the reviewer either"; making both Approvers keeps
those tests exercising *identity* gating (are you the named reviewer?)
rather than accidentally exercising *role* gating (are you an Approver
at all?) when that is not what the test is about.

``dave`` is the admin, granted through ``PLANBENCH_ADMIN_NICKNAMES``:
admin comes from deployment configuration, never from anything a user
can set, and the tests exercise it the same way production does.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from payloads import bordered_map_payload, scenario_payload

from planbench_api.config import get_settings
from planbench_api.main import create_app

ALICE = ("alice", "engineer", "alice-password")
BOB = ("bob", "approver", "bob-password")
CAROL = ("carol", "approver", "carol-password")
ADMIN = ("dave", "engineer", "dave-password")

SEED_USERS = ",".join(f"{nickname}:{role}:{password}" for nickname, role, password in (ALICE, BOB, CAROL, ADMIN))


def isolate_environment(monkeypatch) -> None:
    """Pin every setting the suite depends on.

    ``Settings`` reads ``.env``, so without this the developer's own
    configuration leaks into the tests: a checkout with
    ``PLANBENCH_AGENT_PROVIDER=gemini`` made every agent test fail with a
    503, because the app tried to reach a real provider. These tests
    assert PlanBench's guarantees — auth, the approval gates, citation
    integrity — and must give the same answer on every machine.

    OAuth credentials are blanked for the same reason, and because no
    automated test may ever reach a real provider.
    """
    monkeypatch.setenv("PLANBENCH_SEED_USERS", SEED_USERS)
    monkeypatch.setenv("PLANBENCH_ENABLE_DEV_LOGIN", "true")
    monkeypatch.setenv("PLANBENCH_ADMIN_NICKNAMES", ADMIN[0])
    monkeypatch.setenv("PLANBENCH_ADMIN_EMAILS", "")
    # On by default here so run_benchmark() and friends can clear the
    # spec gate without a second account; TestAdminIntervention exercises
    # the disabled case explicitly by overriding this back to false.
    monkeypatch.setenv("PLANBENCH_ADMIN_OVERRIDE_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET", "test-secret-not-used-in-production")
    monkeypatch.setenv("PLANBENCH_JWT_SECRET", "")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "")
    # The deterministic mock: offline, no key, no network.
    monkeypatch.setenv("PLANBENCH_AGENT_PROVIDER", "mock")
    monkeypatch.setenv("PLANBENCH_AGENT_MODEL", "")
    monkeypatch.setenv("PLANBENCH_AGENT_BASE_URL", "")
    monkeypatch.setenv("PLANBENCH_DATABASE_URL", "")
    monkeypatch.setenv("PLANBENCH_MLFLOW_TRACKING_URI", "")


@pytest.fixture
def app(tmp_path, monkeypatch):
    """App with deterministic seed users and an isolated artifact root."""
    isolate_environment(monkeypatch)
    get_settings.cache_clear()
    application = create_app(artifact_dir=str(tmp_path / "artifacts"))
    yield application
    get_settings.cache_clear()


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def login(client: TestClient, credentials: tuple[str, str, str]) -> str:
    nickname, _role, password = credentials
    response = client.post(
        "/api/v1/auth/login",
        data={"username": nickname, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(client: TestClient, credentials: tuple[str, str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, credentials)}"}


@pytest.fixture
def alice_headers(client: TestClient) -> dict[str, str]:
    """The default member: creates things and owns them."""
    return auth_headers(client, ALICE)


@pytest.fixture
def bob_headers(client: TestClient) -> dict[str, str]:
    """Somebody else — the reviewer in most review tests."""
    return auth_headers(client, BOB)


@pytest.fixture
def carol_headers(client: TestClient) -> dict[str, str]:
    """A third member, for "not the reviewer either" cases."""
    return auth_headers(client, CAROL)


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client, ADMIN)


@pytest.fixture
def created_map(client: TestClient, alice_headers: dict[str, str]) -> dict:
    response = client.post("/api/v1/maps", json=bordered_map_payload(), headers=alice_headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def created_scenario(
    client: TestClient, created_map: dict, alice_headers: dict[str, str]
) -> dict:
    response = client.post(
        "/api/v1/scenarios",
        json={"map_id": created_map["id"], "scenario": scenario_payload()},
        headers=alice_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()
