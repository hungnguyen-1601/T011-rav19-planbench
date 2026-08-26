"""API tests: scenarios CRUD and map-dependent validation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from payloads import scenario_payload


class TestScenarios:
    def test_create_and_get(self, client: TestClient, created_scenario: dict) -> None:
        fetched = client.get(f"/api/v1/scenarios/{created_scenario['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["scenario"]["name"] == "api-test-scenario"

    def test_create_with_unknown_map_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/scenarios",
            json={"map_id": "nope", "scenario": scenario_payload()},
        )
        assert response.status_code == 404

    def test_start_inside_wall_rejected(self, client: TestClient, created_map: dict) -> None:
        bad = scenario_payload(start_pose={"x": 0.5, "y": 0.5, "theta": 0.0})
        response = client.post(
            "/api/v1/scenarios", json={"map_id": created_map["id"], "scenario": bad}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert "collides" in str(response.json()["error"]["details"])

    def test_validate_endpoint_reports_errors(self, client: TestClient, created_map: dict) -> None:
        bad = scenario_payload(start_pose={"x": 0.5, "y": 0.5, "theta": 0.0})
        response = client.post(
            "/api/v1/scenarios/validate",
            json={"map_id": created_map["id"], "scenario": bad},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["errors"]

    def test_update_and_delete(self, client: TestClient, created_scenario: dict) -> None:
        updated = client.put(
            f"/api/v1/scenarios/{created_scenario['id']}",
            json={
                "map_id": created_scenario["map_id"],
                "scenario": scenario_payload(name="renamed"),
            },
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert client.delete(f"/api/v1/scenarios/{created_scenario['id']}").status_code == 204


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


class TestPreviewingALibraryEntryStoresNothing:
    """Looking at something must not write it down.

    The obvious way to preview a library entry is to import it and look
    at the rows that come back — and that is how one database reached
    198 maps carrying 41 distinct checksums, 117 of them the same grid.
    """

    def test_the_preview_creates_no_map(self, client: TestClient) -> None:
        before = len(client.get("/api/v1/maps").json())
        response = client.get("/api/v1/scenario-library/sudden_stop/preview")
        assert response.status_code == 200, response.text
        assert len(client.get("/api/v1/maps").json()) == before

    def test_it_returns_the_map_and_the_scenario(self, client: TestClient) -> None:
        body = client.get("/api/v1/scenario-library/sudden_stop/preview").json()
        assert body["library_name"] == "sudden_stop"
        assert body["map"]["width"] > 0
        assert body["scenario"]["start_pose"] != body["scenario"]["goal_pose"]

    def test_traffic_arrives_sampled_over_the_scenarios_own_timeout(
        self, client: TestClient
    ) -> None:
        """The span is what the scenario declares, so what plays is the
        length of episode it asks for and not a number chosen here."""
        body = client.get("/api/v1/scenario-library/sudden_stop/preview?step=1.0").json()
        assert body["step"] == 1.0
        assert abs(body["duration"] - float(body["scenario"]["timeout_seconds"])) <= 1.0
        assert len(body["dynamic_obstacles"][0]["track"]) > 1

    def test_the_sampling_is_the_simulators_own(self, client: TestClient) -> None:
        """A second implementation of the motion laws would drift from
        the simulator's, and a preview that disagrees with the episode is
        worse than no preview."""
        import pytest

        from planbench_schemas.dynamic import DynamicObstacle, position_at

        body = client.get("/api/v1/scenario-library/sudden_stop/preview?step=1.0").json()
        declared = DynamicObstacle.model_validate(body["scenario"]["dynamic_obstacles"][0])
        for index, point in enumerate(body["dynamic_obstacles"][0]["track"][:5]):
            expected = position_at(declared, index * 1.0, 0)
            assert point["x"] == pytest.approx(expected.x)
            assert point["y"] == pytest.approx(expected.y)

    def test_a_scenario_with_no_traffic_previews_anyway(self, client: TestClient) -> None:
        """An empty aisle is a thing to look at, not a reason to refuse."""
        body = client.get("/api/v1/scenario-library/open_space/preview").json()
        assert body["dynamic_obstacles"] == []
        assert body["map"]["width"] > 0

    def test_an_unknown_entry_is_refused_rather_than_invented(self, client: TestClient) -> None:
        assert client.get("/api/v1/scenario-library/not_a_scenario/preview").status_code == 422
