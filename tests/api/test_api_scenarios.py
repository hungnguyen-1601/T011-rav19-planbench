"""API tests: scenarios CRUD and map-dependent validation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from payloads import scenario_payload


class TestScenarios:
    def test_create_and_get(
        self, client: TestClient, created_scenario: dict, alice_headers: dict
    ) -> None:
        fetched = client.get(
            f"/api/v1/scenarios/{created_scenario['id']}", headers=alice_headers
        )
        assert fetched.status_code == 200
        assert fetched.json()["scenario"]["name"] == "api-test-scenario"

    def test_create_with_unknown_map_404(self, client: TestClient, alice_headers: dict) -> None:
        response = client.post(
            "/api/v1/scenarios",
            json={"map_id": "nope", "scenario": scenario_payload()},
            headers=alice_headers,
        )
        assert response.status_code == 404

    def test_start_inside_wall_rejected(
        self, client: TestClient, created_map: dict, alice_headers: dict
    ) -> None:
        bad = scenario_payload(start_pose={"x": 0.5, "y": 0.5, "theta": 0.0})
        response = client.post(
            "/api/v1/scenarios",
            json={"map_id": created_map["id"], "scenario": bad},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert "collides" in str(response.json()["error"]["details"])

    def test_validate_endpoint_reports_errors(
        self, client: TestClient, created_map: dict, alice_headers: dict
    ) -> None:
        bad = scenario_payload(start_pose={"x": 0.5, "y": 0.5, "theta": 0.0})
        response = client.post(
            "/api/v1/scenarios/validate",
            json={"map_id": created_map["id"], "scenario": bad},
            headers=alice_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["errors"]

    def test_update_and_delete(
        self, client: TestClient, created_scenario: dict, alice_headers: dict
    ) -> None:
        updated = client.put(
            f"/api/v1/scenarios/{created_scenario['id']}",
            json={
                "map_id": created_scenario["map_id"],
                "scenario": scenario_payload(name="renamed"),
            },
            headers=alice_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert (
            client.delete(
                f"/api/v1/scenarios/{created_scenario['id']}", headers=alice_headers
            ).status_code
            == 204
        )

    def test_unauthenticated_is_rejected(self, client: TestClient) -> None:
        """The auth gap this router used to have (every endpoint, unguarded)."""
        assert client.get("/api/v1/scenarios").status_code == 401
        assert (
            client.post(
                "/api/v1/scenarios", json={"map_id": "x", "scenario": scenario_payload()}
            ).status_code
            == 401
        )


class TestAlgorithms:
    def test_registry_marks_benchmarkable_stacks(self, client: TestClient) -> None:
        response = client.get("/api/v1/algorithms")
        assert response.status_code == 200
        algorithms = {entry["id"]: entry for entry in response.json()}
        assert algorithms["astar+dwa"]["benchmarkable"] is True
        # The pure-pursuit stack exists only to validate the pipeline.
        assert algorithms["astar+pure_pursuit"]["benchmarkable"] is False
        assert algorithms["astar+dwa"]["config_schema"]["properties"]["weight_clearance"]

    def test_single_algorithm_lookup(self, client: TestClient) -> None:
        assert client.get("/api/v1/algorithms/astar+dwa").json()["id"] == "astar+dwa"
        assert client.get("/api/v1/algorithms/astar+nope").status_code == 422
