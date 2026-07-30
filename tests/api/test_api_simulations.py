"""API tests: simulation sessions and WebSocket streaming."""

from __future__ import annotations

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
        with client.websocket_connect(f"/ws/simulations/{simulation['id']}?speed=50") as websocket:
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
            f"/ws/simulations/{simulation['id']}?speed=1000"
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
            f"/ws/simulations/{simulation['id']}?pace=false"
        ) as websocket:
            _, states, message = drain(websocket)
        assert states == total
        assert message["type"] == "result"

    def test_not_run_yet_reports_error(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario)
        with client.websocket_connect(f"/ws/simulations/{simulation['id']}") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "not_ready"

    def test_unknown_simulation_reports_error(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/simulations/missing") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "not_found"
