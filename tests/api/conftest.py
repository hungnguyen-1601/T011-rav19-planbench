"""Fixtures for API tests: fresh app per test, signed-in clients, resources.

Four accounts, all members. There is no operator and no reviewer any
more — who may do what is decided per benchmark by ownership, so the
fixtures are named after people rather than roles, and a test that needs
"somebody else" reaches for ``bob`` instead of a different role.

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

ALICE = ("alice", "alice-password")
BOB = ("bob", "bob-password")
CAROL = ("carol", "carol-password")
ADMIN = ("dave", "dave-password")

SEED_USERS = ",".join(f"{nickname}:{password}" for nickname, password in (ALICE, BOB, CAROL, ADMIN))


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
    # Uploaded models go to a per-test directory. Without this they
    # would land in the developer's checkout and leak between cases.
    monkeypatch.setenv("PLANBENCH_MODEL_DIR", str(tmp_path / "models"))
    get_settings.cache_clear()
    application = create_app(artifact_dir=str(tmp_path / "artifacts"))
    yield application
    get_settings.cache_clear()


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def login(client: TestClient, credentials: tuple[str, str]) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": credentials[0], "password": credentials[1]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(client: TestClient, credentials: tuple[str, str]) -> dict[str, str]:
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
def created_map(client: TestClient) -> dict:
    response = client.post("/api/v1/maps", json=bordered_map_payload())
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def created_scenario(client: TestClient, created_map: dict) -> dict:
    response = client.post(
        "/api/v1/scenarios",
        json={"map_id": created_map["id"], "scenario": scenario_payload()},
    )
    assert response.status_code == 201, response.text
    return response.json()
