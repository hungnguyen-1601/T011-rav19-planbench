"""API tests: health, maps CRUD and validation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from payloads import bordered_map_payload


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestMaps:
    def test_create_and_get(self, client: TestClient, alice_headers: dict) -> None:
        payload = bordered_map_payload()
        created = client.post("/api/v1/maps", json=payload, headers=alice_headers)
        assert created.status_code == 201
        body = created.json()
        assert body["version"] == 1
        assert body["checksum"]
        fetched = client.get(f"/api/v1/maps/{body['id']}", headers=alice_headers)
        assert fetched.status_code == 200
        assert fetched.json()["map_data"]["name"] == "api-test-map"

    def test_list_returns_summaries(
        self, client: TestClient, created_map: dict, alice_headers: dict
    ) -> None:
        response = client.get("/api/v1/maps", headers=alice_headers)
        assert response.status_code == 200
        summaries = response.json()
        assert len(summaries) == 1
        assert summaries[0]["id"] == created_map["id"]
        assert "cells" not in str(summaries[0])  # summaries exclude the grid

    def test_update_bumps_version(
        self, client: TestClient, created_map: dict, alice_headers: dict
    ) -> None:
        payload = bordered_map_payload(name="renamed")
        response = client.put(
            f"/api/v1/maps/{created_map['id']}", json=payload, headers=alice_headers
        )
        assert response.status_code == 200
        assert response.json()["version"] == 2

    def test_delete(self, client: TestClient, created_map: dict, alice_headers: dict) -> None:
        assert (
            client.delete(f"/api/v1/maps/{created_map['id']}", headers=alice_headers).status_code
            == 204
        )
        assert (
            client.get(f"/api/v1/maps/{created_map['id']}", headers=alice_headers).status_code
            == 404
        )

    def test_unknown_map_404_with_error_shape(
        self, client: TestClient, alice_headers: dict
    ) -> None:
        response = client.get("/api/v1/maps/doesnotexist", headers=alice_headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_invalid_map_schema_422(self, client: TestClient, alice_headers: dict) -> None:
        payload = bordered_map_payload()
        payload["cells"] = payload["cells"][:-1]  # wrong length
        response = client.post("/api/v1/maps", json=payload, headers=alice_headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "request_validation_error"

    def test_rotated_origin_rejected(self, client: TestClient, alice_headers: dict) -> None:
        payload = bordered_map_payload()
        payload["origin"]["theta"] = 0.5
        response = client.post("/api/v1/maps", json=payload, headers=alice_headers)
        assert response.status_code == 422

    def test_validate_endpoint(self, client: TestClient, alice_headers: dict) -> None:
        response = client.post(
            "/api/v1/maps/validate", json=bordered_map_payload(), headers=alice_headers
        )
        assert response.status_code == 200
        assert response.json() == {"valid": True, "errors": []}

    def test_unauthenticated_is_rejected(self, client: TestClient) -> None:
        """The auth gap this router used to have (F: no auth at all)."""
        assert client.get("/api/v1/maps").status_code == 401
        assert client.post("/api/v1/maps", json=bordered_map_payload()).status_code == 401


def _pgm(rows: list[list[int]]) -> bytes:
    height, width = len(rows), len(rows[0])
    header = f"P5\n{width} {height}\n255\n".encode("ascii")
    return header + bytes(v for row in rows for v in row)


class TestImportRos:
    """F01: import a map in the ROS map_server format (PGM + YAML)."""

    def test_imports_a_pgm_and_yaml_pair(self, client: TestClient, alice_headers: dict) -> None:
        image = _pgm([[0, 0, 0], [0, 255, 0], [0, 0, 0]])
        yaml_text = "resolution: 0.1\norigin: [0.0, 0.0, 0.0]\n"
        response = client.post(
            "/api/v1/maps/import-ros",
            headers=alice_headers,
            data={"name": "ros-import"},
            files={
                "image": ("map.pgm", image, "application/octet-stream"),
                "yaml": ("map.yaml", yaml_text, "application/x-yaml"),
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["map_data"]["name"] == "ros-import"
        assert body["map_data"]["width"] == 3
        assert body["map_data"]["height"] == 3
        # Border occupied, centre free — matches the pixel grid above.
        assert body["map_data"]["cells"][4] == 0  # centre, FREE

    def test_malformed_yaml_is_a_422_not_a_500(
        self, client: TestClient, alice_headers: dict
    ) -> None:
        response = client.post(
            "/api/v1/maps/import-ros",
            headers=alice_headers,
            data={"name": "bad"},
            files={
                "image": ("map.pgm", _pgm([[255]]), "application/octet-stream"),
                "yaml": ("map.yaml", "not: valid: yaml: [", "application/x-yaml"),
            },
        )
        assert response.status_code == 422

    def test_unauthenticated_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/maps/import-ros",
            data={"name": "x"},
            files={
                "image": ("map.pgm", _pgm([[255]]), "application/octet-stream"),
                "yaml": ("map.yaml", "resolution: 0.1\norigin: [0,0,0]\n", "application/x-yaml"),
            },
        )
        assert response.status_code == 401
