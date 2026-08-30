"""API tests: simulation sessions and WebSocket streaming."""

from __future__ import annotations

from blocked_route import blocked_scenario, two_doorway_map
from conftest import ws_url
from fastapi.testclient import TestClient


def create_simulation(client: TestClient, created_map: dict, created_scenario: dict) -> dict:
    response = client.post(
        "/api/v1/simulations",
        json={"map_id": created_map["id"], "scenario_id": created_scenario["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestSimulations:
    def test_create_and_run(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario)
        assert simulation["state"] == "created"
        run = client.post(f"/api/v1/simulations/{simulation['id']}/run")
        assert run.status_code == 200
        body = run.json()
        assert body["state"] == "finished"
        assert body["result"]["status"] == "success"
        assert body["metrics"]["success"] is True
        assert len(body["result"]["trajectory"]) > 10

    def test_result_endpoint(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario)
        empty = client.get(f"/api/v1/simulations/{simulation['id']}/result")
        assert empty.status_code == 200
        assert empty.json()["result"] is None
        client.post(f"/api/v1/simulations/{simulation['id']}/run")
        full = client.get(f"/api/v1/simulations/{simulation['id']}/result")
        assert full.json()["result"]["status"] == "success"

    def test_run_twice_conflicts(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario)
        client.post(f"/api/v1/simulations/{simulation['id']}/run")
        again = client.post(f"/api/v1/simulations/{simulation['id']}/run")
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "invalid_state"

    def test_unknown_algorithm_rejected(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        response = client.post(
            "/api/v1/simulations",
            json={
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithm": "astar+teleport",
            },
        )
        assert response.status_code == 422


class TestReplanningOverTheApi:
    """`/simulate` is the page people watch a robot get stuck on.

    Until this wiring existed, the only way to reach the replanning code
    was a benchmark: the simulation service called ``run_stack`` without
    the rule and there was no field to put it in. A test that only
    checked the field round-trips would have passed on that broken
    version, so the premise test here runs a genuinely blocked route and
    demands the outcome change.
    """

    def _blocked(self, client: TestClient) -> tuple[str, str]:
        map_response = client.post("/api/v1/maps", json=two_doorway_map().model_dump(mode="json"))
        assert map_response.status_code == 201, map_response.text
        map_id = map_response.json()["id"]
        scenario_response = client.post(
            "/api/v1/scenarios",
            json={"map_id": map_id, "scenario": blocked_scenario().model_dump(mode="json")},
        )
        assert scenario_response.status_code == 201, scenario_response.text
        return map_id, scenario_response.json()["id"]

    def _run(self, client: TestClient, map_id: str, scenario_id: str, **body) -> dict:
        created = client.post(
            "/api/v1/simulations",
            json={"map_id": map_id, "scenario_id": scenario_id, **body},
        )
        assert created.status_code == 201, created.text
        run = client.post(f"/api/v1/simulations/{created.json()['id']}/run")
        assert run.status_code == 200, run.text
        return run.json()

    def test_a_blocked_robot_stays_blocked_without_it(self, client: TestClient) -> None:
        """The control. Without this the next test proves nothing."""
        map_id, scenario_id = self._blocked(client)
        body = self._run(client, map_id, scenario_id)
        assert body["result"]["status"] == "stuck"
        assert body["metrics"]["replan_count"] == 0

    def test_the_same_run_reaches_the_goal_with_it(self, client: TestClient) -> None:
        map_id, scenario_id = self._blocked(client)
        body = self._run(
            client,
            map_id,
            scenario_id,
            replanning={"enabled": True, "max_replans": 3},
        )
        assert body["result"]["status"] == "success"
        assert body["metrics"]["replan_count"] >= 1
        # The event is what the replay timeline draws its marker from.
        assert any(event["type"] == "replan" for event in body["result"]["events"])

    def test_the_rule_is_echoed_back_on_the_resource(self, client: TestClient) -> None:
        map_id, scenario_id = self._blocked(client)
        created = client.post(
            "/api/v1/simulations",
            json={
                "map_id": map_id,
                "scenario_id": scenario_id,
                "replanning": {"enabled": True, "max_replans": 2},
            },
        )
        assert created.json()["replanning"] == {"enabled": True, "max_replans": 2}
        fetched = client.get(f"/api/v1/simulations/{created.json()['id']}")
        assert fetched.json()["replanning"] == {"enabled": True, "max_replans": 2}

    def test_a_payload_that_never_mentions_it_runs_with_it_off(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        """Simulations stored before this field existed must still run."""
        simulation = create_simulation(client, created_map, created_scenario)
        assert simulation["replanning"] == {"enabled": False, "max_replans": 0}
        body = client.post(f"/api/v1/simulations/{simulation['id']}/run").json()
        assert body["metrics"]["replan_count"] == 0

    def test_enabled_with_a_zero_budget_is_refused_with_a_readable_reason(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        response = client.post(
            "/api/v1/simulations",
            json={
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "replanning": {"enabled": True, "max_replans": 0},
            },
        )
        assert response.status_code == 422
        # A switch that turns nothing on would make the stored run claim
        # a capability it never used; the message has to say so.
        assert "does nothing" in response.text


def drain(websocket) -> tuple[dict, int, dict]:
    """Read start message, count state frames, return the final message."""
    first = websocket.receive_json()
    states = 0
    message = websocket.receive_json()
    while message["type"] == "state":
        states += 1
        message = websocket.receive_json()
    return first, states, message


class TestWebSocket:
    def test_streams_states_then_result(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario)
        client.post(f"/api/v1/simulations/{simulation['id']}/run")
        # speed=50: ~11.5 s of simulation replays in ~0.23 s of real time,
        # yielding >5 state frames under the 60 Hz rate cap.
        with client.websocket_connect(
            ws_url(client, f"/ws/simulations/{simulation['id']}", speed="50")
        ) as websocket:
            first, states, message = drain(websocket)
            assert first["type"] == "start"
            assert first["plan_path"]
            assert states > 5
            assert message["type"] == "result"
            assert message["status"] == "success"
            assert message["metrics"]["success"] is True

    def test_paced_stream_skips_frames_at_high_speed(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario)
        run = client.post(f"/api/v1/simulations/{simulation['id']}/run").json()
        total = len(run["result"]["trajectory"])
        with client.websocket_connect(
            ws_url(client, f"/ws/simulations/{simulation['id']}", speed="1000")
        ) as websocket:
            _, states, message = drain(websocket)
        assert message["type"] == "result"
        assert states < total  # rate cap drops frames rather than delaying them

    def test_unpaced_stream_delivers_every_frame(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        """pace=false is what the web UI uses: no server throttling, so the
        client can pace playback itself without losing trajectory points."""
        simulation = create_simulation(client, created_map, created_scenario)
        run = client.post(f"/api/v1/simulations/{simulation['id']}/run").json()
        total = len(run["result"]["trajectory"])
        with client.websocket_connect(
            ws_url(client, f"/ws/simulations/{simulation['id']}", pace="false")
        ) as websocket:
            _, states, message = drain(websocket)
        assert states == total
        assert message["type"] == "result"

    def test_not_run_yet_reports_error(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario)
        with client.websocket_connect(
            ws_url(client, f"/ws/simulations/{simulation['id']}")
        ) as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "not_ready"

    def test_unknown_simulation_reports_error(self, client: TestClient) -> None:
        with client.websocket_connect(ws_url(client, "/ws/simulations/missing")) as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "not_found"
