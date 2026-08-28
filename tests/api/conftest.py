"""Fixtures for API tests: fresh app per test, signed-in clients, resources.

Four accounts. Three hold the business packages an ordinary member needs
(engineer + reviewer, so one person can both create work and answer a
review request without the fixtures having to invent a fifth account);
``dave`` additionally holds ``admin`` through ``PLANBENCH_ADMIN_NICKNAMES``,
because admin comes from deployment configuration and the tests exercise
it the way production does. They are named after people rather than after
roles, so a test needing "somebody else" reaches for ``bob``.

**``client`` is signed in as alice.** That is the change contract 7.0.0
forced: reading a trace, a report or a stored map now needs an account,
so an anonymous client is no longer the ordinary case — it is the
special one. Tests that are *about* anonymity take ``anonymous`` instead,
and that spelling is deliberate: it makes "this asserts a 401" visible in
the signature rather than hidden in the absence of a header.

Per-request headers still win, so ``headers=auth_headers(client, BOB)``
behaves exactly as it did.
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
#: Engineer and nothing else. The account that proves a package really
#: does stop somewhere: alice and bob carry reviewer as well, so a test
#: asking "is this refused to somebody without the capability?" needs
#: somebody who genuinely lacks it.
ENGINEER = ("erin", "erin-password")

#: Engineer and reviewer together, because most fixtures need to create
#: work *and* the test then needs somebody able to review it. The
#: packages do not nest, so this has to be said rather than implied.
MEMBER_ROLES = "engineer+reviewer"

SEED_USERS = ",".join(
    [
        *(
            f"{nickname}:{MEMBER_ROLES}:{password}"
            for nickname, password in (ALICE, BOB, CAROL, ADMIN)
        ),
        f"{ENGINEER[0]}:engineer:{ENGINEER[1]}",
    ]
)


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
    # Seed roles are honoured on single-person profiles only, and the
    # suite needs them honoured. The alternative — granting through the
    # admin API in a fixture — would make every test depend on the very
    # routes several of them exist to check.
    monkeypatch.setenv("PLANBENCH_DEPLOYMENT_PROFILE", "desktop-single-user")
    monkeypatch.setenv("PLANBENCH_SEPARATION_OF_DUTIES", "strict")
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
def anonymous(app) -> TestClient:
    """Nobody. For the tests that assert a route refuses a stranger."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(app) -> TestClient:
    """Signed in as alice, because reading now needs an account."""
    signed_in = TestClient(app, raise_server_exceptions=False)
    signed_in.headers.update(auth_headers(signed_in, ALICE))
    return signed_in


def login(client: TestClient, credentials: tuple[str, str]) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": credentials[0], "password": credentials[1]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(client: TestClient, credentials: tuple[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, credentials)}"}


def ws_url(client: TestClient, path: str, **params: str) -> str:
    """A socket URL carrying a fresh one-time ticket.

    A browser cannot set a header on a WebSocket, so the socket takes a
    ticket minted over ordinary HTTP instead of the bearer token — the
    token would otherwise be written into every access log along the
    path, valid for the next hour. Tests go through the same door.
    """
    response = client.post("/api/v1/ws/tickets")
    assert response.status_code == 200, response.text
    query = "&".join(
        [f"ticket={response.json()['ticket']}", *(f"{k}={v}" for k, v in params.items())]
    )
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}{query}"


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
def engineer_headers(client: TestClient) -> dict[str, str]:
    """Somebody holding the engineer package and nothing else."""
    return auth_headers(client, ENGINEER)


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
