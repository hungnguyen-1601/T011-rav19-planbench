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

    def test_delete_archives_rather_than_removes(
        self, client: TestClient, created_map: dict
    ) -> None:
        """The verb stays DELETE; the row stays too.

        A map is referenced by scenarios, task profiles and every run
        made against it. Removing the row turns each of those into a
        dangling id, so what a caller means by "delete" — take it off my
        list — is served by archiving, and fetching it by id still
        answers so a stored run can still say what it ran on.
        """
        map_id = created_map["id"]
        assert client.delete(f"/api/v1/maps/{map_id}").status_code == 204
        assert map_id not in [row["id"] for row in client.get("/api/v1/maps").json()]
        assert client.get(f"/api/v1/maps/{map_id}").status_code == 200

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

    def test_it_needs_a_login(self, anonymous: TestClient, map_id: str) -> None:
        """It writes files, and files outlive the request that made them."""
        assert anonymous.post(f"/api/v1/maps/{map_id}/materialise").status_code == 401

    def test_an_unknown_map_is_a_404(self, client, alice_headers):
        response = client.post("/api/v1/maps/doesnotexist/materialise", headers=alice_headers)
        assert response.status_code == 404

    def test_it_reads_the_id_and_version_out_of_the_path(self) -> None:
        """One reader for the one filename shape this module invents.

        The recovery needs it to know which version was asked for, and the
        pins endpoint needs it to say which deployments are stuck on an
        old one. Parsing it in both places would be two definitions of the
        same convention, free to disagree.
        """
        from planbench_api.map_files import pinned_map_reference

        assert pinned_map_reference("maps/custom/abc123__v2.pgm") == ("abc123", 2)
        # The sidecar names the same pin as the image.
        assert pinned_map_reference("maps/custom/abc123__v2.yaml") == ("abc123", 2)
        assert pinned_map_reference("maps/custom/abc123__v12.pgm") == ("abc123", 12)

        # Nothing that is not a pinned custom map.
        assert pinned_map_reference("maps/open_hall.pgm") is None
        assert pinned_map_reference("maps/custom/no_version.pgm") is None
        assert pinned_map_reference("maps/custom/abc__vX.pgm") is None
        assert pinned_map_reference(None) is None
        assert pinned_map_reference("") is None

    def test_recovery_refuses_to_serve_a_different_version(
        self, client, alice_headers, map_id
    ) -> None:
        """**The version in the filename is the point of the filename.**

        A deployment pinned to ``__v1`` keeps pointing at the walls its
        episodes were driven on. If that file goes missing — a container
        restart, a fresh checkout — recovery used to write whatever the
        row holds *now* under the old name, so the deployment silently
        began measuring a world it never agreed to while every stored
        trace beside it kept claiming to describe the same place.

        Nobody is watching when this runs, which is exactly why it has to
        refuse rather than guess. A refusal is recoverable; a wrong grid
        is not.
        """
        from planbench_api.map_files import ensure_custom_map_files

        pinned = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        pinned_path = REPO_ROOT / pinned["map"]
        assert pinned_path.is_file()

        # The map moves on, exactly as editing it in the UI would.
        payload = bordered_map_payload()
        payload["cells"][payload["width"] + 1] = 100
        bumped = client.put(f"/api/v1/maps/{map_id}", json=payload, headers=alice_headers)
        assert bumped.status_code == 200, bumped.text
        assert bumped.json()["version"] == 2

        pinned_path.unlink()
        (REPO_ROOT / pinned["map_yaml"]).unlink()

        recovered = ensure_custom_map_files(pinned["map"], REPO_ROOT, client.app.state.repos.maps)
        assert recovered is False, "v2's grid must not be written under v1's name"
        assert not pinned_path.is_file(), "refusing means writing nothing at all"

    def test_recovery_still_works_when_the_version_matches(
        self, client, alice_headers, map_id
    ) -> None:
        """The guard is about the version, not about recovery itself.

        The ordinary case — the file vanished and the store still holds
        exactly that version — has to keep working, or a container
        restart becomes an outage.
        """
        from planbench_api.map_files import ensure_custom_map_files

        resp = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        (REPO_ROOT / resp["map"]).unlink()
        (REPO_ROOT / resp["map_yaml"]).unlink()

        assert ensure_custom_map_files(resp["map"], REPO_ROOT, client.app.state.repos.maps)
        assert (REPO_ROOT / resp["map"]).is_file()

    def test_ensure_custom_map_files_recreates_missing_file(self, client, alice_headers, map_id):
        """If ephemeral maps/custom/ files are purged after container restart,
        ensure_custom_map_files automatically reconstructs them from database."""
        from planbench_api.map_files import ensure_custom_map_files

        resp = client.post(f"/api/v1/maps/{map_id}/materialise", headers=alice_headers).json()
        map_path = REPO_ROOT / resp["map"]
        yaml_path = REPO_ROOT / resp["map_yaml"]
        assert map_path.is_file()
        assert yaml_path.is_file()

        # Simulate ephemeral file deletion (container restart / cache purge)
        map_path.unlink()
        yaml_path.unlink()
        assert not map_path.is_file()

        # Ensure auto materialisation works
        app = client.app
        map_repo = app.state.repos.maps
        recreated = ensure_custom_map_files(resp["map"], REPO_ROOT, map_repo)
        assert recreated is True
        assert map_path.is_file()
        assert yaml_path.is_file()


class TestWhichDeploymentsRunThisMap:
    """The question the map editor could not answer.

    A deployment names its map by path and the path carries the version,
    so a map edited after a deployment was filed leaves that deployment
    on the old walls. That is deliberate — ``episode_context_id`` does
    not hash the map (HĐ-3.1), so moving a deployment silently would make
    every stored run describe a world that no longer exists.

    What was missing was anybody being told. Somebody edited a map,
    re-ran the bench, and watched it measure the old grid with nothing on
    screen to say why.
    """

    @pytest.fixture
    def map_id(self, client: TestClient, alice_headers: dict[str, str]) -> str:
        created = client.post("/api/v1/maps", json=bordered_map_payload(), headers=alice_headers)
        assert created.status_code == 201, created.text
        return created.json()["id"]

    def _profile_on(self, client, headers, map_id: str, profile_id: str) -> dict:
        """File a deployment whose map is this stored map, at its version."""
        materialised = client.post(f"/api/v1/maps/{map_id}/materialise", headers=headers).json()
        base = client.get("/api/v1/task-profiles/template", headers=headers).json()
        base["id"] = profile_id
        base["environment"]["map"] = materialised["map"]
        base["environment"]["map_yaml"] = materialised["map_yaml"]
        filed = client.post("/api/v1/task-profiles", json=base, headers=headers)
        assert filed.status_code in (200, 201), filed.text
        return filed.json()

    def test_a_map_nobody_deployed_has_no_pins(self, client, alice_headers, map_id) -> None:
        answered = client.get(f"/api/v1/maps/{map_id}/pins", headers=alice_headers)
        assert answered.status_code == 200, answered.text
        body = answered.json()
        assert body["current_version"] == 1
        assert body["pins"] == []

    def test_it_reports_a_deployment_as_current_until_the_map_moves(
        self, client, alice_headers, map_id
    ) -> None:
        self._profile_on(client, alice_headers, map_id, "pins_probe_v1")

        body = client.get(f"/api/v1/maps/{map_id}/pins", headers=alice_headers).json()
        mine = [pin for pin in body["pins"] if pin["task_profile_id"] == "pins_probe_v1"]
        assert len(mine) == 1
        assert mine[0]["pinned_version"] == 1
        assert mine[0]["stale"] is False

        # Edit the map. The deployment does not follow, and that is the
        # whole design — but now it can be said out loud.
        payload = bordered_map_payload()
        payload["cells"][payload["width"] + 1] = 100
        assert (
            client.put(f"/api/v1/maps/{map_id}", json=payload, headers=alice_headers).status_code
            == 200
        )

        body = client.get(f"/api/v1/maps/{map_id}/pins", headers=alice_headers).json()
        assert body["current_version"] == 2
        mine = [pin for pin in body["pins"] if pin["task_profile_id"] == "pins_probe_v1"]
        assert mine[0]["pinned_version"] == 1
        assert mine[0]["stale"] is True, "the deployment is behind and has to say so"

    def test_stale_deployments_are_listed_first(self, client, alice_headers, map_id) -> None:
        """Ordered by what the reader came here to find.

        A map with a dozen deployments on it is a list nobody reads to the
        end; the one that is behind is the answer to the question that
        brought them.
        """
        self._profile_on(client, alice_headers, map_id, "pins_old")
        payload = bordered_map_payload()
        payload["cells"][payload["width"] + 1] = 100
        client.put(f"/api/v1/maps/{map_id}", json=payload, headers=alice_headers)
        self._profile_on(client, alice_headers, map_id, "pins_new")

        pins = client.get(f"/api/v1/maps/{map_id}/pins", headers=alice_headers).json()["pins"]
        by_id = {pin["task_profile_id"]: pin for pin in pins}
        assert by_id["pins_old"]["stale"] is True
        assert by_id["pins_new"]["stale"] is False
        assert pins[0]["stale"] is True, "the stale one is what the reader is looking for"

    def test_a_deployment_on_a_bundled_map_pins_nothing(
        self, client, alice_headers, map_id
    ) -> None:
        """Only custom maps carry a version in their path.

        A profile naming a bundled map is not pinned to a row in this
        store at all, and reporting it as a pin would invite somebody to
        "update" a map the editor never held.
        """
        body = client.get(f"/api/v1/maps/{map_id}/pins", headers=alice_headers).json()
        assert all(pin["task_profile_id"] != "open_hall_v2" for pin in body["pins"])

    def test_it_needs_an_account(self, anonymous, map_id) -> None:
        assert anonymous.get(f"/api/v1/maps/{map_id}/pins").status_code == 401

    def test_an_unknown_map_is_a_404(self, client, alice_headers) -> None:
        assert (
            client.get("/api/v1/maps/doesnotexist/pins", headers=alice_headers).status_code == 404
        )


class TestStagingDoesNotFileACopyPerClick:
    """A map is its occupancy, and the name was never part of that.

    Staging reuses the stored row holding the walls it is about to run.
    It used to decide that by comparing whole ``MapData`` documents, and
    that comparison could never be true: the map it holds has been
    written out as a map_server pair and read back, and a map read from
    disk takes its ``name`` from the image file's stem —
    ``b92f3f964633__v1`` where the stored row says ``sudden-stop``.

    Same walls, same resolution, same origin, different name. So every
    press of "show me the world" filed another row, and the copies then
    went on to confuse the *next* lookup: once the original had been
    edited, a stale duplicate was what the scan found first. That is the
    whole reason a bench kept running walls somebody had already
    replaced.
    """

    def test_a_map_off_disk_differs_from_its_row_by_name_alone(
        self, client, alice_headers, tmp_path
    ) -> None:
        """The fact the old comparison tripped over.

        Written as a test rather than a comment because it is the reason
        the rule below has to be about the checksum: if the round trip
        ever became lossless, somebody would reasonably ask why the
        cheaper equality was not good enough.
        """
        from planbench_api.map_files import materialise_map
        from planbench_benchmark.task_map import load_environment_map
        from planbench_schemas.task_profile import EnvironmentSpec

        created = client.post("/api/v1/maps", json=bordered_map_payload(), headers=alice_headers)
        stored = client.app.state.repos.maps.get(created.json()["id"])
        pgm, sidecar = materialise_map(stored, tmp_path)
        loaded = load_environment_map(EnvironmentSpec(map=pgm, map_yaml=sidecar), base_dir=tmp_path)

        assert loaded != stored.map_data, "if this ever passes, revisit the rule below"
        assert loaded.name != stored.map_data.name, "the stem is where the new name comes from"
        # `checksum()` hashes the name as well, so it moves too — which
        # is exactly why the reuse rule below cannot be built on it.
        assert loaded.checksum() != stored.map_data.checksum()
        # Field by field, so a future change that breaks the grid itself
        # is not mistaken for this known, harmless difference.
        assert loaded.cells == stored.map_data.cells
        assert loaded.width == stored.map_data.width
        assert loaded.height == stored.map_data.height
        assert loaded.resolution == stored.map_data.resolution

    def test_staging_reuses_the_stored_map_instead_of_shadowing_it(
        self, client, alice_headers
    ) -> None:
        """The first staging is where the copy used to appear.

        Comparing whole documents, the map read off disk never equalled
        the row it had been written from — the name had changed — so the
        first staging filed a second row holding the same walls under the
        file's stem. The *second* staging then matched that shadow, which
        is why "stage twice, get one row" was true even while every
        deployment was quietly growing a duplicate of its own map.

        So the assertion is about the row count before and after **one**
        staging, and about which id comes back: the map somebody can find
        in the editor, not a copy named after a file.
        """
        # Big enough for the template's missions: the point here is the
        # map row, and a map they fall outside of would be refused on
        # validation before staging ever reached it.
        created = client.post(
            "/api/v1/maps",
            json=bordered_map_payload(width=30, height=14),
            headers=alice_headers,
        )
        assert created.status_code == 201, created.text
        map_id = created.json()["id"]

        materialised = client.post(
            f"/api/v1/maps/{map_id}/materialise", headers=alice_headers
        ).json()
        base = client.get("/api/v1/task-profiles/template", headers=alice_headers).json()
        base["id"] = "staging_dupe_probe"
        base["environment"]["map"] = materialised["map"]
        base["environment"]["map_yaml"] = materialised["map_yaml"]
        filed = client.post("/api/v1/task-profiles", json=base, headers=alice_headers)
        assert filed.status_code in (200, 201), filed.text
        missions = filed.json()["profile"].get("missions") or []
        assert missions, "needs a mission to stage"

        before = len(client.get("/api/v1/maps", headers=alice_headers).json())
        staged = client.post(
            f"/api/v1/task-profiles/staging_dupe_probe/test-bench",
            json={
                "mission_id": missions[0]["id"],
                "seed": 7,
                "stack": "astar+dwa",
                "local_config": "dwa_coarse",
            },
            headers=alice_headers,
        )
        assert staged.status_code == 201, staged.text
        after = len(client.get("/api/v1/maps", headers=alice_headers).json())

        assert staged.json()["map_id"] == map_id, (
            "staging must point at the stored map, not at a copy named after its file"
        )
        assert after == before, f"staging filed a shadow map row: {before} -> {after}"
