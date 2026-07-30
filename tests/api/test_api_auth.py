"""API tests: JWT authentication and role-based access control."""

from __future__ import annotations

from conftest import ADMIN, OPERATOR, REVIEWER, auth_headers
from fastapi.testclient import TestClient


class TestLogin:
    def test_valid_credentials_return_a_token(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login", data={"username": OPERATOR[0], "password": OPERATOR[1]}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["role"] == "operator"
        assert body["access_token"]
        assert body["expires_in"] > 0

    def test_wrong_password_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login", data={"username": OPERATOR[0], "password": "wrong"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_unknown_user_rejected(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/login", data={"username": "nobody", "password": "x"})
        assert response.status_code == 401

    def test_me_returns_the_caller(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/me", headers=auth_headers(client, REVIEWER))
        assert response.status_code == 200
        assert response.json() == {"username": REVIEWER[0], "role": "reviewer"}


class TestAccessControl:
    def test_benchmarks_require_authentication(self, client: TestClient) -> None:
        response = client.get("/api/v1/benchmarks")
        assert response.status_code == 401

    def test_invalid_token_rejected(self, client: TestClient) -> None:
        response = client.get("/api/v1/benchmarks", headers={"Authorization": "Bearer not-a-token"})
        assert response.status_code == 401

    def test_reviewer_cannot_create_benchmarks(
        self, client: TestClient, created_map: dict, created_scenario: dict, reviewer_headers
    ) -> None:
        response = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "nope",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=reviewer_headers,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"

    def test_admin_may_act_in_any_role(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        response = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "admin-created",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=auth_headers(client, ADMIN),
        )
        assert response.status_code == 201
