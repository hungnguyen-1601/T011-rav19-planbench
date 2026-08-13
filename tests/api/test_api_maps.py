"""API tests: health, maps CRUD and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from payloads import bordered_map_payload

from planbench_schemas.map_io import load_map_server

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestMaps:
    def test_create_and_get(self, client: TestClient) -> None:
        payload = bordered_map_payload()
        created = client.post("/api/v1/maps", json=payload)
        assert created.status_code == 201
        body = created.json()
        assert body["version"] == 1
        assert body["checksum"]
        fetched = client.get(f"/api/v1/maps/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["map_data"]["name"] == "api-test-map"

    def test_list_returns_summaries(self, client: TestClient, created_map: dict) -> None:
        response = client.get("/api/v1/maps")
        assert response.status_code == 200
        summaries = response.json()
        assert len(summaries) == 1
        assert summaries[0]["id"] == created_map["id"]
        assert "cells" not in str(summaries[0])  # summaries exclude the grid

    def test_update_bumps_version(self, client: TestClient, created_map: dict) -> None:
        payload = bordered_map_payload(name="renamed")
        response = client.put(f"/api/v1/maps/{created_map['id']}", json=payload)
        assert response.status_code == 200
        assert response.json()["version"] == 2

    def test_delete(self, client: TestClient, created_map: dict) -> None:
        assert client.delete(f"/api/v1/maps/{created_map['id']}").status_code == 204
        assert client.get(f"/api/v1/maps/{created_map['id']}").status_code == 404

    def test_unknown_map_404_with_error_shape(self, client: TestClient) -> None:
        response = client.get("/api/v1/maps/doesnotexist")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_invalid_map_schema_422(self, client: TestClient) -> None:
        payload = bordered_map_payload()
        payload["cells"] = payload["cells"][:-1]  # wrong length
        response = client.post("/api/v1/maps", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "request_validation_error"

    def test_rotated_origin_rejected(self, client: TestClient) -> None:
        payload = bordered_map_payload()
        payload["origin"]["theta"] = 0.5
        response = client.post("/api/v1/maps", json=payload)
        assert response.status_code == 422

    def test_validate_endpoint(self, client: TestClient) -> None:
        response = client.post("/api/v1/maps/validate", json=bordered_map_payload())
        assert response.status_code == 200
        assert response.json() == {"valid": True, "errors": []}


class TestTurningAStoredMapIntoTheTwoPathsAProfileNames:
    """The step between drawing a map and running on it.

    A task profile names its map by *path* (HĐ-2); the editor keeps grids
    in the database. Nothing bridged the two, so a map somebody painted
    could be saved and never evaluated on.
    """

    @pytest.fixture
    def map_id(self, client: TestClient, alice_headers: dict[str, str]) -> str:
        created = client.post("/api/v1/maps", json=bordered_map_payload(), headers=alice_headers)
        assert created.status_code == 201, created.text
        return created.json()["id"]

    def test_it_returns_paths_relative_to_the_map_root(
        self, client, alice_headers, map_id, tmp_path, monkeypatch
    ):
        """Relative, never absolute. A profile carrying an absolute path
        is a profile that is only true on one machine, and HĐ-13 asks
        somebody else to rebuild the run from what it says."""
        response = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        for value in (body["map"], body["map_yaml"]):
            assert not Path(value).is_absolute()
            assert value.startswith("maps/custom/")
            assert (REPO_ROOT / value).is_file()

    def test_the_written_pair_reads_back_as_the_same_map(self, client, alice_headers, map_id):
        """The whole point of the crossing: what lands on disk has to be
        the map that was in the store, not a lossy rendering of it."""
        body = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        stored = client.get(f"/api/v1/maps/{map_id}").json()["map_data"]
        loaded = load_map_server(
            (REPO_ROOT / body["map"]).read_bytes(),
            (REPO_ROOT / body["map_yaml"]).read_text(encoding="utf-8"),
            name=stored["name"],
        )
        assert list(loaded.cells) == list(stored["cells"])
        assert loaded.width == stored["width"] and loaded.height == stored["height"]

    def test_calling_it_twice_writes_the_same_answer(self, client, alice_headers, map_id):
        """The name is (map id, version), so a repeat is the same bytes
        at the same path. A caller that fails validation afterwards
        therefore leaves nothing to clean up."""
        first = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        again = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        assert first == again

    def test_editing_the_map_moves_it_to_a_new_file(self, client, alice_headers, map_id):
        """A deployment filed from v1 must keep pointing at v1's walls —
        otherwise its stored traces stop being evidence of a run that
        happened somewhere."""
        before = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        edited = bordered_map_payload()
        edited["cells"][edited["width"] + 1] = 100
        assert (
            client.put(f"/api/v1/maps/{map_id}", json=edited, headers=alice_headers).status_code
            == 200
        )
        after = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        assert after != before
        # And the old file is still there for the deployment that named it.
        assert (REPO_ROOT / before["map"]).is_file()

    def test_it_needs_a_login(self, client: TestClient, map_id: str) -> None:
        """It writes files. Reading a map does not need a login; leaving
        two of them on the server's disk does."""
        assert client.post(f"/api/v1/maps/{map_id}/materialise").status_code == 401

    def test_an_unknown_map_is_a_404(self, client, alice_headers):
        response = client.post("/api/v1/maps/doesnotexist/materialise", headers=alice_headers)
        assert response.status_code == 404
