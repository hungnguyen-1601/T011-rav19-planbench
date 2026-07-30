"""Fixtures for API tests: fresh app per test, auth clients, resources."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from payloads import bordered_map_payload, scenario_payload

from planbench_api.config import get_settings
from planbench_api.main import create_app

OPERATOR = ("op-alice", "operator-password")
OPERATOR2 = ("op-bob", "operator2-password")
REVIEWER = ("rev-carol", "reviewer-password")
ADMIN = ("admin-dave", "admin-password")

SEED_USERS = ",".join(
    [
        f"{OPERATOR[0]}:operator:{OPERATOR[1]}",
        f"{OPERATOR2[0]}:operator:{OPERATOR2[1]}",
        f"{REVIEWER[0]}:reviewer:{REVIEWER[1]}",
        f"{ADMIN[0]}:admin:{ADMIN[1]}",
    ]
)


@pytest.fixture
def app(tmp_path, monkeypatch):
    """App with deterministic seed users and an isolated artifact root."""
    monkeypatch.setenv("PLANBENCH_SEED_USERS", SEED_USERS)
    monkeypatch.setenv("PLANBENCH_JWT_SECRET", "test-secret-not-used-in-production")
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
def operator_headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client, OPERATOR)


@pytest.fixture
def operator2_headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client, OPERATOR2)


@pytest.fixture
def reviewer_headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client, REVIEWER)


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
