"""API tests: simulation sessions and WebSocket streaming."""

from __future__ import annotations

from conftest import ALICE, login
from fastapi.testclient import TestClient


def create_simulation(
    client: TestClient, created_map: dict, created_scenario: dict, headers: dict
) -> dict:
    response = client.post(
        "/api/v1/simulations",
        json={"map_id": created_map["id"], "scenario_id": created_scenario["id"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestSimulations:
    def test_create_and_run(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        assert simulation["state"] == "created"
        run = client.post(f"/api/v1/simulations/{simulation['id']}/run", headers=alice_headers)
        assert run.status_code == 200
        body = run.json()
        assert body["state"] == "finished"
        assert body["result"]["status"] == "success"
        assert body["metrics"]["success"] is True
        assert len(body["result"]["trajectory"]) > 10

    def test_result_endpoint(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        empty = client.get(f"/api/v1/simulations/{simulation['id']}/result", headers=alice_headers)
        assert empty.status_code == 200
        assert empty.json()["result"] is None
        client.post(f"/api/v1/simulations/{simulation['id']}/run", headers=alice_headers)
        full = client.get(f"/api/v1/simulations/{simulation['id']}/result", headers=alice_headers)
        assert full.json()["result"]["status"] == "success"

    def test_run_twice_conflicts(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        client.post(f"/api/v1/simulations/{simulation['id']}/run", headers=alice_headers)
        again = client.post(f"/api/v1/simulations/{simulation['id']}/run", headers=alice_headers)
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "invalid_state"

    def test_unknown_algorithm_rejected(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        response = client.post(
            "/api/v1/simulations",
            json={
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithm": "astar+teleport",
            },
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_unauthenticated_is_rejected(
        self, client: TestClient, created_map: dict, created_scenario: dict
    ) -> None:
        """The auth gap this router used to have (every endpoint, unguarded)."""
        response = client.post(
            "/api/v1/simulations",
            json={"map_id": created_map["id"], "scenario_id": created_scenario["id"]},
        )
        assert response.status_code == 401


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
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        client.post(f"/api/v1/simulations/{simulation['id']}/run", headers=alice_headers)
        token = login(client, ALICE)
        # speed=50: ~11.5 s of simulation replays in ~0.23 s of real time,
        # yielding >5 state frames under the 60 Hz rate cap.
        with client.websocket_connect(
            f"/ws/simulations/{simulation['id']}?speed=50&token={token}"
        ) as websocket:
            first, states, message = drain(websocket)
            assert first["type"] == "start"
            assert first["plan_path"]
            assert states > 5
            assert message["type"] == "result"
            assert message["status"] == "success"
            assert message["metrics"]["success"] is True

    def test_paced_stream_skips_frames_at_high_speed(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        run = client.post(f"/api/v1/simulations/{simulation['id']}/run", headers=alice_headers).json()
        total = len(run["result"]["trajectory"])
        token = login(client, ALICE)
        with client.websocket_connect(
            f"/ws/simulations/{simulation['id']}?speed=1000&token={token}"
        ) as websocket:
            _, states, message = drain(websocket)
        assert message["type"] == "result"
        assert states < total  # rate cap drops frames rather than delaying them

    def test_unpaced_stream_delivers_every_frame(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        """pace=false is what the web UI uses: no server throttling, so the
        client can pace playback itself without losing trajectory points."""
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        run = client.post(f"/api/v1/simulations/{simulation['id']}/run", headers=alice_headers).json()
        total = len(run["result"]["trajectory"])
        token = login(client, ALICE)
        with client.websocket_connect(
            f"/ws/simulations/{simulation['id']}?pace=false&token={token}"
        ) as websocket:
            _, states, message = drain(websocket)
        assert states == total
        assert message["type"] == "result"

    def test_not_run_yet_reports_error(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        token = login(client, ALICE)
        with client.websocket_connect(
            f"/ws/simulations/{simulation['id']}?token={token}"
        ) as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "not_ready"

    def test_unknown_simulation_reports_error(self, client: TestClient) -> None:
        token = login(client, ALICE)
        with client.websocket_connect(f"/ws/simulations/missing?token={token}") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "not_found"

    def test_missing_token_is_rejected(
        self, client: TestClient, created_map: dict, created_scenario: dict, alice_headers: dict
    ) -> None:
        simulation = create_simulation(client, created_map, created_scenario, alice_headers)
        with client.websocket_connect(f"/ws/simulations/{simulation['id']}") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "unauthorized"
