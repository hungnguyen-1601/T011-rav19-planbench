"""The model registry over HTTP: upload, compatibility, ownership.

The fixture checkpoint is a *real* zip with the members Stable-Baselines3
writes, built in memory — a few hundred bytes, never committed. It is
enough to exercise storage, checksums, the structural check and the
whole benchmark path, and it deliberately contains no weights: nothing
in this suite ever deserialises an uploaded file, which is the same rule
the production code follows.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def checkpoint(members: dict[str, bytes] | None = None) -> bytes:
    """A zip shaped like an SB3 checkpoint."""
    payload = members or {
        "data": json.dumps({"policy_class": "MlpPolicy"}).encode(),
        "policy.pth": b"\x00" * 64,
        "pytorch_variables.pth": b"\x00" * 16,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in payload.items():
            archive.writestr(name, content)
    return buffer.getvalue()


METADATA = {
    "framework": "stable-baselines3",
    "framework_version": "2.9.0",
    "algorithm": "PPO",
    "observation": {
        "type": "lidar_goal_velocity",
        # The encoding the policy was trained against. Declaring it is
        # what lets the loader refuse a mismatch instead of feeding the
        # policy a layout it has never seen.
        "version": "v1",
        "shape": [34],
        "lidar_beams": 24,
        "includes_goal_direction": True,
        "includes_current_velocity": True,
    },
    "action": {
        "type": "continuous_velocity",
        "reward_version": "v1",
        "shape": [2],
        "fields": ["linear_velocity", "angular_velocity"],
    },
    "robot": {"radius": 0.3, "max_linear_velocity": 1.0, "max_angular_velocity": 2.0},
    "training": {"environment": "dynamic_warehouse", "total_timesteps": 1_000_000},
}


@pytest.fixture
def profile_id(client: TestClient, alice_headers) -> str:
    """The seeded default robot. A first upload must not start with
    "invent a robot"."""
    profiles = client.get("/api/v1/robot-profiles", headers=alice_headers).json()
    assert profiles, "a default robot profile should be seeded"
    return profiles[0]["id"]


def upload(
    client: TestClient,
    headers: dict,
    profile_id: str,
    *,
    name: str = "warehouse-ppo",
    version: str = "1",
    filename: str = "model.zip",
    data: bytes | None = None,
    metadata: dict | None = METADATA,
):
    files = {
        "model_file": (filename, data if data is not None else checkpoint(), "application/zip")
    }
    if metadata is not None:
        files["metadata_file"] = ("meta.json", json.dumps(metadata).encode(), "application/json")
    return client.post(
        "/api/v1/models/upload",
        headers=headers,
        data={"name": name, "version": version, "robot_profile_id": profile_id},
        files=files,
    )


class TestUpload:
    def test_a_valid_checkpoint_is_stored_and_checked(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        response = upload(client, alice_headers, profile_id)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["validation_status"] == "structural"
        assert body["file_size"] > 0
        # 64 hex characters: the SHA-256 that makes "which model ran?"
        # answerable later.
        assert len(body["checksum"]) == 64
        assert body["is_owner"] is True

    def test_the_metadata_sidecar_describes_the_shapes(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        body = upload(client, alice_headers, profile_id).json()
        assert body["observation_schema"]["lidar_beams"] == 24
        assert body["action_schema"]["fields"] == ["linear_velocity", "angular_velocity"]
        assert body["training_steps"] == 1_000_000
        assert body["training_environment"] == "dynamic_warehouse"

    def test_a_model_uploads_fine_without_a_sidecar(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        # The sidecar is optional; the robot profile fills the gap.
        response = upload(client, alice_headers, profile_id, metadata=None)
        assert response.status_code == 201, response.text
        assert response.json()["observation_schema"]["type"] == "lidar_goal_velocity"

    def test_the_response_never_contains_a_file_path(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        """The whole point: a client cannot learn where files live."""
        body = upload(client, alice_headers, profile_id).text
        assert "storage_key" not in body
        assert "model_path" not in body
        assert "/models/" not in body

    def test_the_same_name_and_version_twice_is_refused(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        upload(client, alice_headers, profile_id, name="dup", version="1")
        again = upload(client, alice_headers, profile_id, name="dup", version="1")
        assert again.status_code == 422
        assert "version" in again.json()["error"]["message"]

    def test_a_new_version_of_the_same_name_is_fine(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        assert upload(client, alice_headers, profile_id, name="v", version="1").status_code == 201
        assert upload(client, alice_headers, profile_id, name="v", version="2").status_code == 201

    def test_an_unknown_robot_profile_is_a_404(self, client: TestClient, alice_headers) -> None:
        assert upload(client, alice_headers, "no-such-profile").status_code == 404


class TestUploadIsPicky:
    """Everything a hostile or mistaken upload can be."""

    @pytest.mark.parametrize("filename", ["payload.py", "run.sh", "model.exe", "notes.pdf", "x"])
    def test_only_zip_is_accepted_as_a_model(
        self, client: TestClient, alice_headers, profile_id, filename: str
    ) -> None:
        response = upload(client, alice_headers, profile_id, filename=filename)
        assert response.status_code == 422
        message = response.json()["error"]["message"]
        assert ".zip" in message
        # The message explains what a PPO model *is*, because the whole
        # confusion this guards against is "I have a PDF about it".
        assert "Stable-Baselines3" in message

    def test_a_pdf_named_zip_is_still_rejected(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        # The extension is a claim; the magic bytes are the file itself.
        response = upload(
            client, alice_headers, profile_id, filename="report.zip", data=b"%PDF-1.7\nnot a zip"
        )
        assert response.status_code == 201, "stored, but flagged"
        body = response.json()
        assert body["validation_status"] == "failed"
        assert "not a zip archive" in body["validation_message"]

    def test_an_archive_without_sb3_members_is_flagged(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        data = checkpoint({"holiday-photos.jpg": b"\xff\xd8\xff"})
        body = upload(client, alice_headers, profile_id, data=data).json()
        assert body["validation_status"] == "failed"
        assert "Stable-Baselines3" in body["validation_message"]

    def test_a_corrupt_archive_is_flagged_not_crashed(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        broken = bytearray(checkpoint())
        broken[20:40] = b"\x00" * 20
        body = upload(client, alice_headers, profile_id, data=bytes(broken)).json()
        assert body["validation_status"] == "failed"

    def test_a_traversal_filename_cannot_escape(
        self, client: TestClient, alice_headers, profile_id, tmp_path
    ) -> None:
        response = upload(client, alice_headers, profile_id, filename="../../../../etc/passwd.zip")
        assert response.status_code == 201
        # Nothing outside the model directory, and the stored name is
        # the basename with the separators gone.
        written = list((tmp_path / "models").rglob("*.zip"))
        assert written, "the file should have been stored somewhere"
        for path in written:
            assert path.is_relative_to(tmp_path / "models")
        assert any(path.name == "passwd.zip" for path in written)

    def test_a_windows_traversal_filename_is_also_flattened(
        self, client: TestClient, alice_headers, profile_id, tmp_path
    ) -> None:
        response = upload(
            client, alice_headers, profile_id, filename=r"..\..\windows\system32\evil.zip"
        )
        assert response.status_code == 201
        assert not (tmp_path / "models" / "windows").exists()

    def test_bad_metadata_flags_the_model_without_losing_it(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        # A model whose sidecar claims the wrong algorithm is still
        # stored — the file may be fine and the description fixable.
        wrong = {**METADATA, "algorithm": "SAC"}
        body = upload(client, alice_headers, profile_id, metadata=wrong).json()
        assert body["validation_status"] == "failed"
        assert "PPO" in body["validation_message"]

    def test_metadata_that_is_not_json_is_reported(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        response = client.post(
            "/api/v1/models/upload",
            headers=alice_headers,
            data={"name": "bad-meta", "robot_profile_id": profile_id},
            files={
                "model_file": ("m.zip", checkpoint(), "application/zip"),
                "metadata_file": ("meta.json", b"{not json", "application/json"),
            },
        )
        assert response.status_code == 201
        assert "not valid JSON" in response.json()["validation_message"]

    def test_upload_requires_a_signed_in_member(self, client: TestClient, profile_id) -> None:
        response = client.post(
            "/api/v1/models/upload",
            data={"name": "anon", "robot_profile_id": profile_id},
            files={"model_file": ("m.zip", checkpoint(), "application/zip")},
        )
        assert response.status_code == 401


class TestCompatibility:
    def test_a_matching_model_is_compatible(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert report["status"] == "compatible"
        assert report["errors"] == []

    def test_an_undeclared_encoding_is_a_warning_not_a_refusal(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        """Most uploads will not declare it. Refusing them would be
        worse than saying what the risk is."""
        metadata = {**METADATA, "observation": {**METADATA["observation"], "version": ""}}
        model_id = upload(client, alice_headers, profile_id, metadata=metadata).json()["id"]
        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert report["status"] == "warning"
        assert report["errors"] == []
        assert any("observation encoding" in warning for warning in report["warnings"])

    def test_a_lidar_mismatch_is_explained_in_words(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        """The message names both numbers, so the fix is obvious."""
        metadata = {**METADATA, "observation": {**METADATA["observation"], "lidar_beams": 36}}
        model_id = upload(client, alice_headers, profile_id, metadata=metadata).json()["id"]
        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert report["status"] == "incompatible"
        assert any("36" in error and "24" in error for error in report["errors"])

    def test_a_three_action_model_is_incompatible(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        metadata = {**METADATA, "action": {**METADATA["action"], "shape": [3]}}
        model_id = upload(client, alice_headers, profile_id, metadata=metadata).json()["id"]
        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert report["status"] == "incompatible"
        assert any("two" in error for error in report["errors"])

    def test_a_camera_model_is_incompatible(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        metadata = {**METADATA, "observation": {"type": "camera_rgb", "shape": [3, 64, 64]}}
        model_id = upload(client, alice_headers, profile_id, metadata=metadata).json()["id"]
        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert report["status"] == "incompatible"
        assert any("camera_rgb" in error for error in report["errors"])

    def test_a_disabled_model_is_incompatible(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        client.patch(
            f"/api/v1/models/{model_id}", json={"status": "disabled"}, headers=alice_headers
        )
        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert report["status"] == "incompatible"
        assert any("disabled" in error for error in report["errors"])

    def test_a_changed_file_is_caught_by_checksum(
        self, client: TestClient, alice_headers, profile_id, tmp_path
    ) -> None:
        """The strongest signal: the bytes are not the bytes we recorded."""
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        stored = next((tmp_path / "models").rglob("model.zip"))
        stored.write_bytes(checkpoint({"data": b"tampered", "policy.pth": b"different"}))

        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert report["status"] == "incompatible"
        assert any("checksum" in error for error in report["errors"])

    def test_a_missing_file_is_caught(
        self, client: TestClient, alice_headers, profile_id, tmp_path
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        next((tmp_path / "models").rglob("model.zip")).unlink()
        report = client.get(
            f"/api/v1/models/{model_id}/compatibility", headers=alice_headers
        ).json()
        assert any("missing" in error for error in report["errors"])

    def test_revalidate_notices_a_missing_file(
        self, client: TestClient, alice_headers, profile_id, tmp_path
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        next((tmp_path / "models").rglob("model.zip")).unlink()
        body = client.post(f"/api/v1/models/{model_id}/validate", headers=alice_headers).json()
        assert body["validation_status"] == "failed"
        assert "missing" in body["validation_message"]


class TestOwnership:
    def test_anyone_can_see_and_use_a_model(
        self, client: TestClient, alice_headers, bob_headers, profile_id
    ) -> None:
        # Sharing is the default: a benchmark platform whose models are
        # private to their uploader cannot compare anything.
        upload(client, alice_headers, profile_id)
        seen = client.get("/api/v1/models", headers=bob_headers).json()
        assert len(seen) == 1
        assert seen[0]["is_owner"] is False

    def test_another_member_cannot_delete_it(
        self, client: TestClient, alice_headers, bob_headers, profile_id
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        response = client.delete(f"/api/v1/models/{model_id}", headers=bob_headers)
        assert response.status_code == 403
        assert "owner" in response.json()["error"]["message"]

    def test_another_member_cannot_disable_it(
        self, client: TestClient, alice_headers, bob_headers, profile_id
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        response = client.patch(
            f"/api/v1/models/{model_id}", json={"status": "disabled"}, headers=bob_headers
        )
        assert response.status_code == 403

    def test_the_owner_can_delete_an_unused_model(
        self, client: TestClient, alice_headers, profile_id, tmp_path
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        assert client.delete(f"/api/v1/models/{model_id}", headers=alice_headers).status_code == 204
        assert client.get(f"/api/v1/models/{model_id}", headers=alice_headers).status_code == 404
        # And the bytes are gone, not orphaned on disk.
        assert not list((tmp_path / "models").rglob("model.zip"))

    def test_an_admin_can_delete_somebody_elses_model(
        self, client: TestClient, alice_headers, admin_headers, profile_id
    ) -> None:
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        assert client.delete(f"/api/v1/models/{model_id}", headers=admin_headers).status_code == 204

    def test_an_invented_model_id_is_a_404(self, client: TestClient, alice_headers) -> None:
        assert client.get("/api/v1/models/deadbeef", headers=alice_headers).status_code == 404


class TestRobotProfiles:
    def test_a_default_profile_is_seeded(self, client: TestClient, alice_headers) -> None:
        profiles = client.get("/api/v1/robot-profiles", headers=alice_headers).json()
        assert profiles[0]["name"] == "Default AMR"
        assert profiles[0]["lidar_beams"] == 24

    def test_seeding_happens_once(self, client: TestClient, alice_headers) -> None:
        client.get("/api/v1/robot-profiles", headers=alice_headers)
        profiles = client.get("/api/v1/robot-profiles", headers=alice_headers).json()
        assert len([p for p in profiles if p["name"] == "Default AMR"]) == 1

    def test_a_member_can_create_one(self, client: TestClient, alice_headers) -> None:
        response = client.post(
            "/api/v1/robot-profiles",
            headers=alice_headers,
            json={
                "name": "Big AMR",
                "radius": 0.5,
                "max_linear_velocity": 1.5,
                "max_angular_velocity": 2.5,
                "lidar_beams": 36,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["lidar_beams"] == 36

    def test_negative_dimensions_are_refused(self, client: TestClient, alice_headers) -> None:
        response = client.post(
            "/api/v1/robot-profiles",
            headers=alice_headers,
            json={
                "name": "Impossible",
                "radius": -1,
                "max_linear_velocity": 1.0,
                "max_angular_velocity": 1.0,
            },
        )
        assert response.status_code == 422

    def test_another_member_cannot_edit_mine(
        self, client: TestClient, alice_headers, bob_headers
    ) -> None:
        created = client.post(
            "/api/v1/robot-profiles",
            headers=alice_headers,
            json={
                "name": "Mine",
                "radius": 0.3,
                "max_linear_velocity": 1.0,
                "max_angular_velocity": 2.0,
            },
        ).json()
        response = client.patch(
            f"/api/v1/robot-profiles/{created['id']}",
            headers=bob_headers,
            json={
                "name": "Hijacked",
                "radius": 0.3,
                "max_linear_velocity": 1.0,
                "max_angular_velocity": 2.0,
            },
        )
        assert response.status_code == 403

    def test_a_profile_in_use_cannot_be_deleted(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        upload(client, alice_headers, profile_id)
        response = client.delete(f"/api/v1/robot-profiles/{profile_id}", headers=alice_headers)
        assert response.status_code == 422
        assert "model" in response.json()["error"]["message"]

    def test_cloning_makes_an_independent_copy(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        clone = client.post(
            f"/api/v1/robot-profiles/{profile_id}/clone?name=My+robot", headers=alice_headers
        ).json()
        assert clone["id"] != profile_id
        assert clone["name"] == "My robot"
        assert clone["lidar_beams"] == 24


class TestBenchmarksUseModelIds:
    """The point of the whole feature, end to end."""

    @pytest.fixture
    def scenario(self, client: TestClient, created_map, created_scenario) -> tuple[str, str]:
        return created_map["id"], created_scenario["id"]

    def test_ppo_without_a_model_gets_a_sentence_not_a_traceback(
        self, client: TestClient, alice_headers, scenario
    ) -> None:
        map_id, scenario_id = scenario
        response = client.post(
            "/api/v1/benchmarks",
            headers=alice_headers,
            json={
                "name": "ppo",
                "map_id": map_id,
                "scenario_id": scenario_id,
                "algorithms": [{"id": "astar+ppo"}],
                "seeds": [1],
            },
        )
        assert response.status_code == 422
        message = response.json()["error"]["message"]
        # The old message was "invalid config for 'astar+ppo': ...
        # model_path Field required", which names an internal field.
        assert "model_path" not in message
        assert "Field required" not in message
        assert "PPO model" in message

    def test_a_benchmark_with_a_model_id_is_accepted(
        self, client: TestClient, alice_headers, profile_id, scenario
    ) -> None:
        map_id, scenario_id = scenario
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        response = client.post(
            "/api/v1/benchmarks",
            headers=alice_headers,
            json={
                "name": "ppo by id",
                "map_id": map_id,
                "scenario_id": scenario_id,
                "algorithms": [
                    {"id": "astar+ppo", "config": {"model_id": model_id}},
                ],
                "seeds": [1],
            },
        )
        assert response.status_code == 201, response.text
        # The stored spec keeps the id, not a path: that is what makes
        # the benchmark reproducible.
        config = response.json()["spec"]["algorithms"][0]["config"]
        assert config["model_id"] == model_id
        assert config.get("model_path", "") == ""

    def test_a_legacy_model_path_spec_still_validates(self) -> None:
        """Benchmarks created before the registry must stay readable."""
        from planbench_benchmark import validate_algorithm_config

        parsed = validate_algorithm_config("astar+ppo", {"model_path": "/old/checkpoint.zip"})
        assert parsed.model_path == "/old/checkpoint.zip"
        assert parsed.model_id == ""

    def test_a_spec_with_neither_is_refused(self) -> None:
        from planbench_benchmark.registry import AlgorithmConfigError, validate_algorithm_config

        with pytest.raises(AlgorithmConfigError):
            validate_algorithm_config("astar+ppo", {})

    def test_running_an_incompatible_model_is_refused_before_the_run(
        self, client: TestClient, alice_headers, profile_id, scenario
    ) -> None:
        map_id, scenario_id = scenario
        metadata = {**METADATA, "observation": {**METADATA["observation"], "lidar_beams": 36}}
        model_id = upload(client, alice_headers, profile_id, metadata=metadata).json()["id"]
        benchmark = client.post(
            "/api/v1/benchmarks",
            headers=alice_headers,
            json={
                "name": "mismatched",
                "map_id": map_id,
                "scenario_id": scenario_id,
                "algorithms": [{"id": "astar+ppo", "config": {"model_id": model_id}}],
                "seeds": [1],
            },
        )
        assert benchmark.status_code == 201, "creating a draft is allowed"
        run = client.post(f"/api/v1/benchmarks/{benchmark.json()['id']}/run", headers=alice_headers)
        # Refused at launch, with the reason, rather than producing
        # nonsense numbers from a mismatched policy.
        assert run.status_code == 422
        assert "36" in run.json()["error"]["message"]

    def test_a_model_used_by_a_benchmark_cannot_be_deleted(
        self, client: TestClient, alice_headers, profile_id, scenario
    ) -> None:
        map_id, scenario_id = scenario
        model_id = upload(client, alice_headers, profile_id).json()["id"]
        benchmark = client.post(
            "/api/v1/benchmarks",
            headers=alice_headers,
            json={
                "name": "uses model",
                "map_id": map_id,
                "scenario_id": scenario_id,
                "algorithms": [{"id": "astar+ppo", "config": {"model_id": model_id}}],
                "seeds": [1],
            },
        ).json()
        # Usage is recorded at launch. Torch is not installed here, so
        # the run fails inside the planner — but the *usage record* is
        # written before that, which is what this asserts.
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)

        detail = client.get(f"/api/v1/models/{model_id}", headers=alice_headers).json()
        assert benchmark["id"] in detail["used_by_benchmarks"]
        response = client.delete(f"/api/v1/models/{model_id}", headers=alice_headers)
        assert response.status_code == 422
        assert "reproducible" in response.json()["error"]["message"]


class TestRunningWithoutTheOptionalStack:
    """PPO needs torch, which is gigabytes and therefore optional.

    A server without it must say so in a sentence an operator can act
    on. The failure mode being guarded against is an HTTP 500 with a
    stack trace, which tells the user only that something broke.
    """

    def test_a_server_without_sb3_explains_itself(self, monkeypatch) -> None:
        from planbench_benchmark import registry as benchmark_registry

        # Simulate the optional install being absent. Patching the
        # lookup rather than sys.modules keeps the fake narrow: nothing
        # else in the process is made to believe SB3 is missing.
        monkeypatch.setattr(
            benchmark_registry,
            "find_spec",
            lambda name: None if name == "stable_baselines3" else object(),
        )
        with pytest.raises(benchmark_registry.AlgorithmConfigError) as caught:
            benchmark_registry.build_local_planner("astar+ppo", {"model_path": "/tmp/x.zip"})

        message = str(caught.value)
        assert "not installed" in message
        assert "A* + DWA" in message
        # An operator reading this must not be handed a traceback.
        assert "Traceback" not in message

    def test_the_registry_writes_the_sidecar_the_loader_needs(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        """The loader refuses a checkpoint that does not say which
        observation encoding it was trained on. The registry keeps that
        in its own shape, so it renders the file the loader expects.

        Skipped without the optional RL packages: the versions written
        into the sidecar come from `planbench_rl`, and a server that
        cannot import it cannot run a PPO benchmark anyway."""
        pytest.importorskip("planbench_rl.observation")
        import json as json_module

        from planbench_api.registry_service import ModelRegistryService

        model_id = upload(client, alice_headers, profile_id).json()["id"]
        # The app under test, not the module-level one: the fixture
        # builds its own, with a temporary model directory.
        state = client.app.state
        service = ModelRegistryService(
            state.repos.models, state.repos.robot_profiles, state.model_storage
        )
        record = state.repos.models.get(model_id)
        assert record is not None

        sidecar = json_module.loads(Path(service.sidecar_location(record)).read_text())
        assert sidecar["observation_version"] == "v1"
        assert sidecar["reward_version"] == "v1"
        assert sidecar["model_id"] == model_id
        # Beside the checkpoint, named after it: that is where the
        # loader looks when no explicit path is given.
        assert Path(service.internal_location(record)).with_suffix(".json").exists()


class TestUploadErrorsStayReadable:
    """A malformed upload must answer with a validation error, not a 500.

    Regression: the 422 handler serialised Pydantic's raw error objects,
    and a required `File()` parameter carries the literal `...` as its
    default. `jsonable_encoder` raised `'ellipsis' object is not
    iterable` *while reporting the error*, so the 500 handler took over
    and a plain missing-field mistake reached the client as an opaque
    internal error.
    """

    def test_a_missing_file_is_a_422_not_a_500(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        response = client.post(
            "/api/v1/models/upload",
            headers=alice_headers,
            data={"name": "no-file", "version": "1", "robot_profile_id": profile_id},
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "request_validation_error"

    def test_a_missing_form_field_is_a_422_not_a_500(
        self, client: TestClient, alice_headers
    ) -> None:
        # `robot_profile_id` omitted: the other required field.
        response = client.post(
            "/api/v1/models/upload",
            headers=alice_headers,
            files={"model_file": ("m.zip", checkpoint(), "application/zip")},
            data={"name": "no-profile"},
        )
        assert response.status_code == 422, response.text

    def test_the_details_survive_json_encoding(
        self, client: TestClient, alice_headers, profile_id
    ) -> None:
        """The point of the fix: the body must be serialisable at all."""
        response = client.post(
            "/api/v1/models/upload",
            headers=alice_headers,
            data={"name": "no-file", "robot_profile_id": profile_id},
        )
        body = response.json()["error"]
        assert body["message"] == "invalid request"
        # Round-trips: no object in `details` defeats the encoder.
        assert json.loads(json.dumps(body["details"])) == body["details"]
