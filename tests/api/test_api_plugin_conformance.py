"""Unpacking an imported bundle and running it (P2).

Where P1 asked whether an archive *is* a bundle, this asks whether the
object inside it does what the manifest says. Every test here starts a
real child process running the uploaded planner, which is the whole
point: a suite that stubbed the lane would be checking the stub.

The cases are chosen around one idea — **the ways a broken plugin can
look fine**. A plugin that crashes every tick answers zero velocity
twice and passes a determinism check by being reliably broken; a plugin
that reads a channel it never declared works perfectly until it meets a
deployment that does not offer it. Both are here.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from conftest import ADMIN, ALICE, auth_headers
from test_api_plugin_import import GOOD_MANIFEST, MANIFEST_PATH, default_profile, message

WORKING_PLANNER = """\
class Planner:
    def __init__(self, cruise_speed: float = 0.4) -> None:
        self._cruise = cruise_speed

    @property
    def name(self):
        return "probe"

    @property
    def control_period(self):
        return None

    def reset(self, request) -> None:
        pass

    def step(self, request):
        return {"linear_velocity": self._cruise, "angular_velocity": 0.0}
"""

CLOCK_DEPENDENT_PLANNER = """\
import time


class Planner:
    @property
    def name(self):
        return "probe"

    @property
    def control_period(self):
        return None

    def reset(self, request) -> None:
        pass

    def step(self, request):
        # The failure HD-4 exists for: nothing raises, the statistics
        # just stop measuring the controller.
        return {"linear_velocity": time.time() % 1.0, "angular_velocity": 0.0}
"""

SNOOPING_PLANNER = """\
class Planner:
    @property
    def name(self):
        return "probe"

    @property
    def control_period(self):
        return None

    def reset(self, request) -> None:
        pass

    def step(self, request):
        for envelope in request.get("channels", ()):
            if envelope.get("capability") == "planbench://channel/robot-state@1":
                break
        else:
            raise LookupError("robot-state was not granted, and I need it")
        return {"linear_velocity": 0.1, "angular_velocity": 0.0}
"""

CRASHING_PLANNER = """\
class Planner:
    @property
    def name(self):
        return "probe"

    @property
    def control_period(self):
        return None

    def reset(self, request) -> None:
        pass

    def step(self, request):
        raise RuntimeError("every tick, reliably")
"""


def probe_manifest(**overrides) -> dict:
    manifest = json.loads(json.dumps(GOOD_MANIFEST))
    manifest["runtime"]["profiles"]["subprocess"]["entry_point"] = "vfh_plus:Planner"
    manifest.update(overrides)
    return manifest


def probe_zip(planner: str, *, manifest: dict | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(MANIFEST_PATH, json.dumps(manifest or probe_manifest()))
        archive.writestr("vfh_plus/__init__.py", "from vfh_plus.planner import Planner\n")
        archive.writestr("vfh_plus/planner.py", planner)
    return buffer.getvalue()


def import_probe(client, headers, planner: str, *, manifest: dict | None = None, name="Probe"):
    return client.post(
        "/api/v1/algorithms/plugins",
        data={
            "name": name,
            "version": "1",
            "robot_profile_id": default_profile(client, headers),
        },
        files={
            "bundle": (
                "probe.zip",
                io.BytesIO(probe_zip(planner, manifest=manifest)),
                "application/zip",
            )
        },
        headers=headers,
    )


@pytest.fixture
def admin(client):
    return auth_headers(client, ADMIN)


class TestAPluginThatBehavesIsRecordedAsHavingRun:
    def test_it_reaches_loaded_not_structural(self, client, admin):
        body = import_probe(client, admin, WORKING_PLANNER).json()
        assert body["validation_status"] == "loaded"
        assert "subprocess" in body["validation_message"]

    def test_the_bundle_is_unpacked_where_the_lane_can_import_it(self, client, admin, tmp_path):
        import_probe(client, admin, WORKING_PLANNER)
        unpacked = tmp_path / "artifacts" / "plugins" / "org.vinai.vfh-plus" / "0.1.0"
        assert (unpacked / "vfh_plus" / "planner.py").is_file()
        assert (unpacked / "vfh_plus" / ".planbench-plugin" / "plugin.json").is_file()

    def test_unpacking_the_same_bytes_twice_is_not_a_second_extraction(self, client, admin):
        """Re-validating must be cheap and must not half-rewrite a
        directory the lane may be importing from."""
        bundle_id = import_probe(client, admin, WORKING_PLANNER).json()["id"]
        again = client.post(f"/api/v1/algorithms/plugins/{bundle_id}/validate", headers=admin)
        assert again.status_code == 200
        assert again.json()["validation_status"] == "loaded"


class TestTheWaysABrokenPluginLooksFine:
    def test_a_plugin_that_consults_the_clock_is_caught(self, client, admin):
        """HD-4's failure mode: nothing raises, the numbers just stop
        being about the controller."""
        body = import_probe(client, admin, CLOCK_DEPENDENT_PLANNER).json()
        assert body["validation_status"] == "failed"
        assert "determinism" in body["validation_message"]

    def test_a_plugin_reading_an_undeclared_channel_is_caught(self, client, admin):
        body = import_probe(client, admin, SNOOPING_PLANNER).json()
        assert body["validation_status"] == "failed"

    def test_a_plugin_that_crashes_every_tick_does_not_pass_as_cautious(self, client, admin):
        """In this lane a crash arrives as a safe stop — a well-formed
        zero-velocity command. Two of them are identical, so the
        determinism check is satisfied by a plugin that is reliably
        dead. Something has to read `failure_reason`, and this is the
        test that says something does."""
        body = import_probe(client, admin, CRASHING_PLANNER).json()
        assert body["validation_status"] == "failed"

    def test_a_bundle_whose_module_raises_on_import(self, client, admin):
        body = import_probe(client, admin, "raise RuntimeError('boom')\n").json()
        assert body["validation_status"] == "failed"


class TestWhatIsNotRunIsNotCalledPassing:
    def test_a_capability_this_check_cannot_synthesise_leaves_it_unverified(self, client, admin):
        """`static-costmap` has a shape only a real episode has. Feeding
        the plugin a plausible-looking fake and reporting the result as
        evidence would be worse than not running: the honest answer is
        `structural` plus the capability that stopped it."""
        manifest = probe_manifest(requirements={"all_of": ["planbench://channel/static-costmap@1"]})
        body = import_probe(client, admin, WORKING_PLANNER, manifest=manifest).json()
        assert body["validation_status"] == "structural"
        assert "cannot synthesise" in body["validation_message"]
        assert "static-costmap" in body["validation_message"]

    def test_a_plugin_this_deployment_cannot_serve_is_not_run_either(self, client, admin):
        manifest = probe_manifest(requirements={"all_of": ["human_state_estimates"]})
        body = import_probe(client, admin, WORKING_PLANNER, manifest=manifest).json()
        # The oracle provider exists, so research-policy preflight admits
        # it and the suite does run. What must not happen is a claim that
        # it passed on a deployment that would refuse it in production.
        assert body["validation_status"] in {"loaded", "structural"}


class TestRunningSomebodyElsesCodeIsTheImportPrivilege:
    def test_a_member_cannot_trigger_a_run(self, client, admin):
        bundle_id = import_probe(client, admin, WORKING_PLANNER).json()["id"]
        member = auth_headers(client, ALICE)
        response = client.post(f"/api/v1/algorithms/plugins/{bundle_id}/validate", headers=member)
        assert response.status_code == 403
        assert "administrator" in message(response)


class TestExtractionRefusesToWriteOutsideItsDirectory:
    def test_a_member_resolving_outside_the_target_is_refused(self, tmp_path):
        """P1 rejects escaping names when it reads the table of contents.
        This is the second check, at the moment that could actually
        escape — tested directly because the first check makes it
        unreachable through the API, which is the point of having both.
        """
        from planbench_api.plugin_runtime import BundleInstallError, _extract_safely

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escaped.py", "x = 1\n")
        target = tmp_path / "bundle"
        target.mkdir()
        with (
            zipfile.ZipFile(buffer) as archive,
            pytest.raises(BundleInstallError, match="outside the bundle directory"),
        ):
            _extract_safely(archive, target)
        assert not (tmp_path / "escaped.py").exists()
