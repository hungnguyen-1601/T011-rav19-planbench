"""Importing an algorithm bundle over real HTTP (P1).

The door this suite guards is the one that puts somebody's Python on the
server, so most of these tests are refusals. The two that are not check
that a good bundle registers and that the verdict on it is computed
when it is asked for rather than remembered from upload time.

**Nothing here executes a plugin, and one test says so.** P1 reads an
archive's table of contents and parses one JSON member; if a future
change starts importing bundles to learn about them, the bundle whose
`planner.py` raises on import will stop being registerable and
`test_a_bundle_whose_code_is_broken_still_registers` will fail.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from conftest import ADMIN, ALICE, auth_headers

MANIFEST_PATH = "vfh_plus/.planbench-plugin/plugin.json"

GOOD_MANIFEST = {
    "plugin_api": "1.2.0",
    "id": "org.vinai.vfh-plus",
    "version": "0.1.0",
    "role": "local",
    "runtime": {
        "supported_lanes": ["subprocess"],
        "production_lane": "subprocess",
        "profiles": {
            "subprocess": {
                "protocol": "planbench-subprocess/v1",
                "codec": "json-v1",
                "deadline_policy": "control-period",
                "entry_point": "vfh_plus:VFHPlusPlanner",
            }
        },
    },
    "requirements": {"all_of": ["lidar_2d"]},
    "supports": {
        "action_types": ["continuous-velocity@1"],
        "robot_dynamics": ["differential-drive@1"],
        "execution_models": ["synchronous-step@1"],
    },
    "config_schema": {"type": "object", "properties": {}},
    "requires_global_path": True,
}

PLANNER_SOURCE = """import math


class VFHPlusPlanner:
    \"\"\"Enough of a controller to be checked: deterministic, and it
    reads only the channel the manifest declares.\"\"\"

    def __init__(self, cruise_speed: float = 0.4) -> None:
        self._cruise = cruise_speed
        self._path = ()

    @property
    def name(self):
        return "vfh_plus"

    @property
    def control_period(self):
        return None

    def reset(self, request) -> None:
        self._path = tuple(request.get("global_path", ()))

    def step(self, request):
        ranges = _payload(request, "lidar_2d")
        nearest = min(ranges) if ranges else math.inf
        speed = self._cruise if nearest > 1.0 else 0.0
        return {"linear_velocity": speed, "angular_velocity": 0.0}


def _payload(request, capability):
    for envelope in request.get("channels", ()):
        if envelope.get("capability") == capability:
            return envelope.get("payload")
    raise LookupError(capability + " was not granted")
"""


def bundle_zip(
    members: dict[str, str] | None = None,
    *,
    manifest: dict | None = None,
    manifest_path: str = MANIFEST_PATH,
) -> bytes:
    """A bundle archive, built in memory.

    Defaults to a well-formed one so each test states only its own
    deviation — a test that had to spell out eight correct members to
    make one wrong is a test whose point is buried.
    """
    contents = {
        "vfh_plus/__init__.py": "from vfh_plus.planner import VFHPlusPlanner\n",
        "vfh_plus/planner.py": PLANNER_SOURCE,
        **(members or {}),
    }
    if manifest_path:
        contents[manifest_path] = json.dumps(manifest or GOOD_MANIFEST)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in contents.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def import_bundle(client, headers, data: bytes | None = None, *, name: str = "VFH+") -> object:
    return client.post(
        "/api/v1/algorithms/plugins",
        data={"name": name, "version": "1", "robot_profile_id": default_profile(client, headers)},
        files={
            "bundle": (
                "vfh_plus.zip",
                io.BytesIO(bundle_zip() if data is None else data),
                "application/zip",
            )
        },
        headers=headers,
    )


def message(response) -> str:
    """The error sentence. Errors are `{"error": {"code", "message"}}`."""
    return response.json()["error"]["message"]


def default_profile(client, headers) -> str:
    profiles = client.get("/api/v1/robot-profiles", headers=headers).json()
    return profiles[0]["id"]


@pytest.fixture
def admin(client):
    return auth_headers(client, ADMIN)


@pytest.fixture
def member(client):
    return auth_headers(client, ALICE)


class TestOnlyAdministratorsMayPutCodeOnTheServer:
    def test_a_member_is_refused(self, client, member):
        response = import_bundle(client, member)
        assert response.status_code == 403, response.text
        assert "administrator" in message(response)

    def test_an_administrator_may_import(self, client, admin):
        assert import_bundle(client, admin).status_code == 201

    def test_reading_needs_no_privilege(self, client, admin, member):
        import_bundle(client, admin)
        listed = client.get("/api/v1/algorithms/plugins", headers=member)
        assert listed.status_code == 200
        assert [row["plugin_id"] for row in listed.json()] == ["org.vinai.vfh-plus"]

    def test_anonymous_callers_get_nothing(self, client):
        assert client.get("/api/v1/algorithms/plugins").status_code == 401


class TestTheArchiveIsCheckedBeforeAnythingIsRegistered:
    def test_a_file_that_is_not_a_zip(self, client, admin):
        response = import_bundle(client, admin, b"this is not an archive")
        assert response.status_code == 422
        assert "not a zip archive" in message(response)

    def test_an_archive_with_no_manifest(self, client, admin):
        response = import_bundle(client, admin, bundle_zip(manifest_path=""))
        assert response.status_code == 422
        assert ".planbench-plugin/plugin.json" in message(response)

    def test_two_manifests_are_two_plugins(self, client, admin):
        extra = {"other/.planbench-plugin/plugin.json": json.dumps(GOOD_MANIFEST)}
        response = import_bundle(client, admin, bundle_zip(extra))
        assert response.status_code == 422
        assert "exactly one plugin" in message(response)

    def test_a_manifest_at_the_archive_root_has_no_package_name(self, client, admin):
        response = import_bundle(
            client, admin, bundle_zip(manifest_path=".planbench-plugin/plugin.json")
        )
        assert response.status_code == 422
        assert "Python package" in message(response)

    def test_an_escaping_member_path(self, client, admin):
        response = import_bundle(client, admin, bundle_zip({"../escape.py": "x = 1\n"}))
        assert response.status_code == 422
        assert "unsafe member paths" in message(response)

    def test_unreadable_json(self, client, admin):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(MANIFEST_PATH, "{not json")
        response = import_bundle(client, admin, buffer.getvalue())
        assert response.status_code == 422
        assert "not readable JSON" in message(response)

    def test_a_wrong_extension_is_refused_before_any_bytes_are_written(self, client, admin):
        response = client.post(
            "/api/v1/algorithms/plugins",
            data={
                "name": "VFH+",
                "version": "1",
                "robot_profile_id": default_profile(client, admin),
            },
            files={"bundle": ("planner.py", io.BytesIO(b"x = 1"), "text/x-python")},
            headers=admin,
        )
        assert response.status_code == 422
        assert ".zip" in message(response)


class TestTheManifestMustSuitThisDoor:
    def test_a_global_plugin_is_refused_with_the_lane_reason(self, client, admin):
        manifest = {**GOOD_MANIFEST, "role": "global", "requires_global_path": None}
        response = import_bundle(client, admin, bundle_zip(manifest=manifest))
        assert response.status_code == 422
        assert "has no plan()" in message(response)

    def test_the_in_process_lane_is_refused(self, client, admin):
        manifest = {
            **GOOD_MANIFEST,
            "runtime": {
                "supported_lanes": ["python_in_process"],
                "production_lane": "python_in_process",
                "profiles": {
                    "python_in_process": {
                        "protocol": "planbench-inproc/v1",
                        "codec": "python-object/v1",
                        "deadline_policy": "control-period",
                        "entry_point": "vfh_plus:VFHPlusPlanner",
                    }
                },
            },
        }
        response = import_bundle(client, admin, bundle_zip(manifest=manifest))
        assert response.status_code == 422
        assert "never falls back" in message(response)

    def test_an_entry_point_that_names_another_package(self, client, admin):
        manifest = json.loads(json.dumps(GOOD_MANIFEST))
        manifest["runtime"]["profiles"]["subprocess"]["entry_point"] = "somewhere_else:Planner"
        response = import_bundle(client, admin, bundle_zip(manifest=manifest))
        assert response.status_code == 422
        assert "bundle directory" in message(response)

    def test_an_unknown_capability_keeps_the_sdk_wording(self, client, admin):
        """The SDK's refusal, not a rewrite of it: an author meets the
        same sentence here that the CLI would have given them."""
        manifest = {**GOOD_MANIFEST, "requirements": {"all_of": ["lidar2d"]}}
        response = import_bundle(client, admin, bundle_zip(manifest=manifest))
        assert response.status_code == 422
        assert "lidar2d" in message(response)


class TestIdentityBelongsToTheManifest:
    def test_the_same_plugin_version_cannot_be_imported_twice(self, client, admin):
        assert import_bundle(client, admin, name="VFH+").status_code == 201
        again = import_bundle(client, admin, name="A completely different label")
        assert again.status_code == 422
        assert "already imported" in message(again)

    def test_a_new_manifest_version_is_a_new_bundle(self, client, admin):
        assert import_bundle(client, admin).status_code == 201
        manifest = {**GOOD_MANIFEST, "version": "0.2.0"}
        assert import_bundle(client, admin, bundle_zip(manifest=manifest)).status_code == 201
        assert len(client.get("/api/v1/algorithms/plugins", headers=admin).json()) == 2


class TestWhatRegistrationDoesAndDoesNotClaim:
    def test_a_good_bundle_records_what_the_manifest_declared(self, client, admin):
        body = import_bundle(client, admin).json()
        assert body["plugin_id"] == "org.vinai.vfh-plus"
        assert body["role"] == "local"
        assert body["requirements"] == ["lidar_2d"]

    def test_a_bundle_whose_code_is_broken_still_registers(self, client, admin):
        """Discovery does not import, and this is the test that says so.

        A bundle whose module raises at import time is registered exactly
        as well as any other: the failure belongs to the conformance run,
        against this plugin, rather than to the upload.
        """
        broken = bundle_zip({"vfh_plus/planner.py": "raise RuntimeError('boom')\n"})
        assert import_bundle(client, admin, broken).status_code == 201

    def test_the_verdict_is_computed_when_asked(self, client, admin):
        bundle_id = import_bundle(client, admin).json()["id"]
        detail = client.get(f"/api/v1/algorithms/plugins/{bundle_id}", headers=admin).json()
        assert detail["compatibility"]["state"] == "registered_and_runnable"
        assert detail["compatibility"]["runnable"] is True
        assert detail["compatibility"]["runtime_lane"] == "subprocess"
        assert detail["compatibility"]["evidence_class"] == "production"

    def test_a_capability_this_deployment_does_not_offer_is_named(self, client, admin):
        manifest = {**GOOD_MANIFEST, "requirements": {"all_of": ["human_state_estimates"]}}
        bundle_id = import_bundle(client, admin, bundle_zip(manifest=manifest)).json()["id"]
        detail = client.get(f"/api/v1/algorithms/plugins/{bundle_id}", headers=admin).json()
        report = detail["compatibility"]
        assert report["runnable"] is False
        assert report["missing_capabilities"] == ["human_state_estimates"]
        assert "human_state_estimates" in report["why"]


class TestEditingCannotRewriteWhatRan:
    def test_the_label_may_change(self, client, admin):
        bundle_id = import_bundle(client, admin).json()["id"]
        response = client.patch(
            f"/api/v1/algorithms/plugins/{bundle_id}",
            json={"description": "Vector field histogram plus"},
            headers=admin,
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Vector field histogram plus"

    def test_the_manifest_may_not(self, client, admin):
        bundle_id = import_bundle(client, admin).json()["id"]
        response = client.patch(
            f"/api/v1/algorithms/plugins/{bundle_id}",
            json={"plugin_id": "org.someone.else"},
            headers=admin,
        )
        # Unknown keys are dropped by the request model rather than
        # applied, so the identity is untouched either way.
        assert response.status_code == 200
        assert response.json()["plugin_id"] == "org.vinai.vfh-plus"

    def test_disabling_is_the_retirement_path_and_delete_is_not_offered(self, client, admin):
        bundle_id = import_bundle(client, admin).json()["id"]
        response = client.patch(
            f"/api/v1/algorithms/plugins/{bundle_id}", json={"status": "disabled"}, headers=admin
        )
        assert response.status_code == 200
        assert response.json()["status"] == "disabled"
        paths = client.get("/openapi.json").json()["paths"]
        assert "delete" not in paths["/api/v1/algorithms/plugins/{bundle_id}"]


class TestTheRoutesResolve:
    def test_the_plugin_routes_are_not_swallowed_by_the_catalogue(self, client, admin):
        """`/algorithms/{algorithm_id}` matches `/algorithms/plugins` too.

        Include order decides which wins, so this asserts the outcome
        rather than the order: a reader who moves the include back will
        see a 422 saying "unknown algorithm 'plugins'" and know why.
        """
        response = client.get("/api/v1/algorithms/plugins", headers=admin)
        assert response.status_code == 200
        assert response.json() == []


class TestTheDuplicatedConstantsAgree:
    def test_the_bundle_directory_matches_discovery(self):
        """`plugin_registry` restates two constants rather than importing
        the simulator. A copy that drifted would reject a perfectly good
        bundle with "no manifest found", so the copy is pinned here."""
        from planbench_plugin_sdk import MANIFEST_FILENAME

        from planbench_api import plugin_registry
        from planbench_simulator.host.discovery import BUNDLE_DIRNAME

        assert plugin_registry.BUNDLE_DIRNAME == BUNDLE_DIRNAME
        assert plugin_registry.MANIFEST_FILENAME == MANIFEST_FILENAME

    def test_the_required_lane_is_a_lane_the_host_supports(self):
        from planbench_api.plugin_registry import REQUIRED_LANE
        from planbench_simulator.host.compatibility import HostSupport
        from planbench_simulator.host.runtimes.subprocess_lane import SubprocessRuntime

        assert SubprocessRuntime.lane == REQUIRED_LANE
        assert REQUIRED_LANE in HostSupport().runtime_lanes

    def test_the_supported_roles_are_the_ones_the_lane_can_drive(self):
        """`global` is excluded because `SubprocessPlugin` has no `plan`.

        Asserted against the class rather than restated as a list: when
        somebody adds `plan` for P6, this fails and points at the
        constant that should widen with it.
        """
        from planbench_api.plugin_registry import SUPPORTED_ROLES
        from planbench_simulator.host.runtimes.subprocess_lane import SubprocessPlugin

        assert "global" not in SUPPORTED_ROLES
        assert not hasattr(SubprocessPlugin, "plan")
        assert all(hasattr(SubprocessPlugin, name) for name in ("reset", "step"))


class TestARefusedUploadLeavesNothingBehind:
    def test_no_orphaned_bytes(self, client, admin, tmp_path):
        import_bundle(client, admin, b"this is not an archive")
        written = [path for path in (tmp_path / "models").rglob("*") if path.is_file()]
        assert written == []
