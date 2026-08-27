"""A plugin the platform has never seen, walked down every path.

**Why this file exists.** Four defects in the import path were found by
somebody using the feature, not by the suite that was written for it:
an imported controller had no named configuration and could not be run;
the edit tab said there was nothing to edit while the algorithm sat on
the same screen; it was offered behind A* only, so choosing RRT* made it
vanish; and its stored parameters came back as `null` and crashed its
constructor. Each lived exactly one layer past where the tests stopped —
the import path was covered, and the paths a plugin travels *after*
importing were not.

So this walks a bundle through all of them in one place. The fixture is
deliberately **unlike** the probes used elsewhere:

- its `config_schema` declares several typed properties, so every
  optional field materialises as `null` when a candidate stores it;
- its constructor **validates its arguments**, so a `None` arriving
  where a number belongs raises instead of quietly becoming a default.
  A permissive constructor would have absorbed the crash that made the
  fourth defect visible, and this suite would have passed while the
  platform was still broken.

When adding a path a plugin can travel, add it here too.
"""

from __future__ import annotations

import io
import json
import pathlib
import zipfile

import pytest
from conftest import ADMIN, ALICE, auth_headers
from test_api_plugin_import import default_profile

from planbench_schemas.episode_context import EpisodeContext

PLUGIN_ID = "org.newlab.wall-follower"

#: A controller that is not VFH+ and not the probe: it takes four
#: parameters, checks them, and refuses nonsense loudly.
PLANNER = """\
class WallFollower:
    def __init__(self, standoff_m=0.6, cruise_speed=0.35, turn_gain=1.8, patience=3):
        # Loud on purpose. A constructor that shrugged at None would hide
        # the exact defect this fixture exists to expose.
        for label, value in (
            ("standoff_m", standoff_m),
            ("cruise_speed", cruise_speed),
            ("turn_gain", turn_gain),
            ("patience", patience),
        ):
            if value is None:
                raise TypeError(f"{label} arrived as None; a number was declared")
        if cruise_speed <= 0:
            raise ValueError("cruise_speed must be positive")
        self._standoff = standoff_m
        self._cruise = cruise_speed
        self._gain = turn_gain
        self._patience = int(patience)

    @property
    def name(self):
        return "wall_follower"

    @property
    def control_period(self):
        return None

    def reset(self, request) -> None:
        self._seen = 0

    def step(self, request):
        ranges = _payload(request, "lidar_2d")
        if not ranges:
            return {"linear_velocity": 0.0, "angular_velocity": 0.0}
        ceiling = max(ranges)
        hits = [r for r in ranges if r < ceiling - 1e-6]
        nearest = min(hits) if hits else ceiling
        # Deterministic, and a function of the scan alone.
        error = self._standoff - nearest
        return {
            "linear_velocity": self._cruise if nearest > self._standoff else 0.0,
            "angular_velocity": max(-1.0, min(1.0, self._gain * error)),
        }


def _payload(request, capability):
    for envelope in request.channels:
        if envelope.capability == capability:
            return envelope.payload
    raise LookupError(capability + " was not granted")
"""

MANIFEST = {
    "plugin_api": "1.2.0",
    "id": PLUGIN_ID,
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
                "entry_point": "wall_follower:WallFollower",
            }
        },
    },
    "requirements": {"all_of": ["lidar_2d"]},
    "supports": {
        "action_types": ["continuous-velocity@1"],
        "robot_dynamics": ["differential-drive@1"],
        "execution_models": ["synchronous-step@1"],
    },
    # Four typed properties and no declared defaults — the shape that
    # turns every stored parameter into a null.
    "config_schema": {
        "type": "object",
        "properties": {
            "standoff_m": {"type": "number"},
            "cruise_speed": {"type": "number"},
            "turn_gain": {"type": "number"},
            "patience": {"type": "integer"},
        },
    },
    "requires_global_path": True,
}


INIT_PY = "from wall_follower.planner import WallFollower\n"


def bundle(manifest: dict | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "wall_follower/.planbench-plugin/plugin.json", json.dumps(manifest or MANIFEST)
        )
        archive.writestr("wall_follower/__init__.py", INIT_PY)
        archive.writestr("wall_follower/planner.py", PLANNER)
    return buffer.getvalue()


def do_import(client, headers, manifest: dict | None = None, name: str = "Wall follower"):
    return client.post(
        "/api/v1/algorithms/plugins",
        data={
            "name": name,
            "version": "1",
            "robot_profile_id": default_profile(client, headers),
        },
        files={"bundle": ("wall_follower.zip", io.BytesIO(bundle(manifest)), "application/zip")},
        headers=headers,
    )


@pytest.fixture
def admin(client):
    return auth_headers(client, ADMIN)


@pytest.fixture(autouse=True)
def _clean_catalogue():
    from planbench_benchmark.registry import clear_external

    clear_external()
    yield
    clear_external()


@pytest.fixture
def imported(client, admin):
    """The bundle, imported and conformance-checked. Everything after
    this point is a path it travels once it exists."""
    response = do_import(client, admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["validation_status"] == "loaded", body["validation_message"]
    return body


class TestItArrives:
    def test_the_archive_is_accepted_and_the_plugin_runs(self, imported):
        assert imported["plugin_id"] == PLUGIN_ID
        assert imported["role"] == "local"
        assert imported["requirements"] == ["lidar_2d"]


class TestEveryPickerCanReachIt:
    def test_the_catalogue_lists_it_behind_each_planner(self, client, admin, imported):
        from planbench_benchmark.plugin_stacks import offerable_global_planners

        listed = {row["id"] for row in client.get("/api/v1/algorithms", headers=admin).json()}
        for planner in offerable_global_planners():
            assert f"{planner}+{PLUGIN_ID}" in listed

    def test_the_configuration_picker_lists_it(self, client, admin, imported):
        rows = client.get("/api/v1/local-controllers", headers=admin).json()
        assert [row for row in rows if row["controller"] == PLUGIN_ID]

    def test_the_edit_tab_can_reach_it(self, client, admin, imported):
        """Not a UI test — the data the tab reads. It lists what the
        caller owns, and an imported algorithm has to be in it."""
        rows = client.get("/api/v1/algorithms/plugins", headers=admin).json()
        assert [row for row in rows if row["plugin_id"] == PLUGIN_ID and row["owned"]]

    def test_renaming_it_does_not_touch_its_identity(self, client, admin, imported):
        response = client.patch(
            f"/api/v1/algorithms/plugins/{imported['id']}",
            json={"name": "Renamed", "description": "still the same code"},
            headers=admin,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"
        assert response.json()["plugin_id"] == PLUGIN_ID
        assert response.json()["checksum"] == imported["checksum"]


class TestBothWaysOfRunningIt:
    """The two paths differ in one thing that turned out to matter: one
    stores the parameters and reads them back, and one does not."""

    def test_the_direct_path_builds_a_controller(self, client, admin, imported):
        from planbench_benchmark.registry import build_local_planner

        planner = build_local_planner(f"astar+{PLUGIN_ID}", {})
        assert planner.name == "wall_follower"

    def test_the_stored_path_builds_one_too(self, client, admin, imported):
        """Where the constructor used to receive `None` for every
        declared parameter and raise."""
        from planbench_benchmark.candidates import candidate_from_stack
        from planbench_benchmark.registry import build_local_planner

        stack = f"astar+{PLUGIN_ID}"
        candidate = candidate_from_stack(stack, params={})
        stored = candidate.params[PLUGIN_ID]
        assert stored["cruise_speed"] is None, "the round trip still writes nulls"
        planner = build_local_planner(stack, stored)
        assert planner.name == "wall_follower"

    def test_an_explicit_parameter_reaches_the_constructor(self, client, admin, imported):
        """The other half: filtering nulls must not filter real values.
        A rejected one proves the number arrived."""
        from planbench_benchmark.registry import build_local_planner

        with pytest.raises(Exception, match="cruise_speed"):
            build_local_planner(f"astar+{PLUGIN_ID}", {"cruise_speed": -1.0})

    def test_the_decision_path_does_not_double_wrap_it(self, client, admin, imported):
        """`build_planners` is what a decision run uses, and it is not
        `build_local_planner`.

        It wraps the controller in `LegacyLocalPlugin` to put a plain
        planner behind the host contract — which an imported plugin
        already is. Wrapping it again hid `channel_source`, so
        `run_stack` never bound the channel seam, every tick raised
        inside the plugin, the host turned each into a safe stop, and the
        robot sat at its start pose for a whole 60-second episode while
        replanning fired because it was making no progress.

        The suite missed it because it exercised the direct path only.
        This asserts the shape: whatever comes back must still carry the
        seam the loop looks for.
        """
        from planbench_benchmark.candidates import build_planners, candidate_from_stack

        candidate = candidate_from_stack(f"astar+{PLUGIN_ID}", params={})
        _, local = build_planners(candidate, episode_seed=1)
        assert getattr(local, "channel_source", None) is not None

    def test_the_decision_path_actually_moves_the_robot(
        self, client, admin, imported, created_map, created_scenario
    ):
        """The same check one layer out: a seam that is present but never
        bound looks identical to a working one until something drives.

        **Path length, not displacement.** This fixture is a crude
        controller: it circles rather than navigating, so its net
        displacement is small even when everything works, and asserting
        on that would grade the fixture's skill instead of the platform's
        wiring. What an unbound seam produces is different in kind —
        *every* tick is a safe stop, zero velocity, nothing travelled.
        """
        from planbench_benchmark.candidates import build_planners, candidate_from_stack
        from planbench_benchmark.scenarios import build_scenario
        from planbench_simulator.nav_stack import run_stack

        candidate = candidate_from_stack(f"astar+{PLUGIN_ID}", params={})
        global_planner, local = build_planners(candidate, episode_seed=1)
        map_data, scenario = build_scenario("open_space")
        scenario = scenario.model_copy(update={"timeout_seconds": 20.0})
        run = run_stack(map_data, scenario, local, global_planner)

        points = run.result.trajectory
        travelled = sum(
            ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
            for a, b in zip(points, points[1:], strict=False)
        )
        assert travelled > 1.0, f"the robot never moved ({travelled:.3f} m travelled)"

    def test_a_built_in_still_goes_through_the_wrapper(self, client, admin, imported):
        """The pass-through must be narrow. A plain controller has no
        seam and still needs the legacy adapter."""
        from planbench_benchmark.candidates import build_planners, candidate_from_stack

        candidate = candidate_from_stack("astar+dwa", params=None)
        _, local = build_planners(candidate, episode_seed=1)
        assert getattr(local, "channel_source", None) is None
        assert type(local).__name__ == "HostBackedLocalPlanner"

    def test_a_simulation_drives_it(self, client, admin, imported, created_map, created_scenario):
        created = client.post(
            "/api/v1/simulations",
            json={
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithm": f"astar+{PLUGIN_ID}",
            },
            headers=admin,
        )
        assert created.status_code == 201, created.text
        run = client.post(f"/api/v1/simulations/{created.json()['id']}/run", headers=admin)
        assert run.status_code == 200, run.text
        assert run.json()["result"]["steps"] > 5


class TestTheTraceItLeavesBehind:
    """Writing the episode's trace is a third path, and a third place a
    plugin met a wall.

    A trace file has one schema, fixed before its first row, and the six
    §5.9 latency layers are columns only the subprocess lane produces. The
    recorder was always built without them, so the first episode where an
    imported plugin actually produced commands — rather than the safe
    stops an unbound seam had been producing — was refused at the writer
    with `TraceError: latency layers were supplied to a recorder that was
    not built to write them`.

    Underneath it sat a second one: a recovery step is driven by the loop,
    not by the controller, so its row has no layers at all. Refusing it
    would drop real motion; writing zeros unmarked would claim the
    controller answered in 0 ms and feed that into every percentile.
    """

    def episode(self, tmp_path, stack: str, params):
        import sys

        sys.path.insert(0, str(pathlib.Path("tests").resolve()))
        from task_profile_fakes import make_profile

        from planbench_benchmark.candidates import candidate_from_stack
        from planbench_benchmark.episode import run_contract_episode
        from planbench_schemas.map_io import load_map_server

        profile = make_profile()
        # The profile's own map. Handing it a different one produces a
        # mission whose start and goal are off the grid, one `no_path`
        # row, and a test that asserts nothing about traces.
        root = pathlib.Path(".")
        map_data = load_map_server(
            (root / profile.environment.map).read_bytes(),
            (root / profile.environment.map_yaml).read_text(),
            profile.id,
        )
        candidate = candidate_from_stack(stack, params=params)
        context = EpisodeContext(
            task_profile_id=profile.id, mission_id=profile.missions[0].id, seed=1
        )
        return run_contract_episode(candidate, profile, context, map_data, root=tmp_path)

    def test_an_imported_plugin_can_write_its_trace(self, client, admin, imported, tmp_path):
        import pyarrow.parquet as pq

        path, _ = self.episode(tmp_path, f"astar+{PLUGIN_ID}", {})
        table = pq.read_table(path)
        assert "transport_ms" in table.column_names, "the lane measures layers, so they belong"
        assert table.num_rows > 5

    def test_a_tick_nobody_measured_says_so(self, client, admin, imported, tmp_path):
        """Rather than reporting zero as though it had been timed."""
        import pyarrow.parquet as pq

        from planbench_simulator.trace import NOT_MEASURED

        path, _ = self.episode(tmp_path, f"astar+{PLUGIN_ID}", {})
        table = pq.read_table(path)
        measured_by = table.column("compute_measured_by").to_pylist()
        from planbench_simulator.trace import LATENCY_LAYER_COLUMNS

        layers = [table.column(name).to_pylist() for name in LATENCY_LAYER_COLUMNS]
        assert "plugin" in measured_by, "the plugin drove, so most rows are its measurements"

        # The property, not the vocabulary. Checking only that the labels
        # come from a known set let a mutation relabel the unmeasured row
        # as `host` and still pass — the label was being read, and what it
        # claimed was not.
        for index, label in enumerate(measured_by):
            spent = sum(column[index] for column in layers)
            if spent == 0.0:
                assert label == NOT_MEASURED, (
                    f"row {index} reports no time in any layer but claims {label!r} measured it"
                )

    def test_a_built_in_trace_keeps_the_plain_schema(self, client, admin, imported, tmp_path):
        """The columns are added for the lane that measures them and for
        nothing else: a built-in trace must be byte-comparable with every
        one written before this change."""
        import pyarrow.parquet as pq

        path, _ = self.episode(tmp_path, "astar+dwa", None)
        assert "transport_ms" not in pq.read_table(path).column_names


class TestTheGatesStillApplyToIt:
    def test_the_control_rate_check_can_read_it(self, client, admin, imported):
        """`validate_control_rate` builds the controller to read its
        period. For an imported one that starts a worker, so this asserts
        the gate can run at all rather than that it passes."""
        from planbench_benchmark.candidates import candidate_from_stack
        from planbench_benchmark.registry import build_local_planner

        candidate = candidate_from_stack(f"astar+{PLUGIN_ID}", params={})
        period = build_local_planner(
            f"astar+{PLUGIN_ID}", candidate.params[PLUGIN_ID]
        ).control_period
        assert period is None or period > 0

    def test_the_configuration_name_is_one_registration_accepts(self, client, admin, imported):
        from planbench_benchmark.candidates import offered_controller_configs, validate_config_names

        name = next(iter(offered_controller_configs()[PLUGIN_ID]))
        validate_config_names([(f"astar+{PLUGIN_ID}", name)])

    def test_disabling_it_withdraws_it_everywhere(self, client, admin, imported):
        from planbench_benchmark.candidates import offered_controller_configs

        client.patch(
            f"/api/v1/algorithms/plugins/{imported['id']}",
            json={"status": "disabled"},
            headers=admin,
        )
        listed = {row["id"] for row in client.get("/api/v1/algorithms", headers=admin).json()}
        assert f"astar+{PLUGIN_ID}" not in listed
        assert PLUGIN_ID not in offered_controller_configs()


class TestTheSecondVersionOfIt:
    def test_a_fix_at_a_new_version_is_a_different_candidate(self, client, admin, imported):
        from planbench_benchmark.candidates import candidate_from_stack

        first = candidate_from_stack(f"astar+{PLUGIN_ID}", params={})
        client.patch(
            f"/api/v1/algorithms/plugins/{imported['id']}",
            json={"status": "disabled"},
            headers=admin,
        )
        faster = PLANNER.replace("cruise_speed=0.35", "cruise_speed=0.75")
        assert faster != PLANNER
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "wall_follower/.planbench-plugin/plugin.json",
                json.dumps({**MANIFEST, "version": "0.2.0"}),
            )
            archive.writestr(
                "wall_follower/__init__.py", "from wall_follower.planner import WallFollower\n"
            )
            archive.writestr("wall_follower/planner.py", faster)
        response = client.post(
            "/api/v1/algorithms/plugins",
            data={
                "name": "Wall follower",
                "version": "2",
                "robot_profile_id": default_profile(client, admin),
            },
            files={"bundle": ("wf.zip", io.BytesIO(buffer.getvalue()), "application/zip")},
            headers=admin,
        )
        assert response.status_code == 201, response.text
        second = candidate_from_stack(f"astar+{PLUGIN_ID}", params={})
        assert first.candidate_id != second.candidate_id


class TestReplacingItWithChangedCode:
    """Change the code, upload it again, done — no editing the manifest.

    The loop this platform exists for, and the one the first identity
    rule made awkward: keying on the manifest's declared version meant an
    author had to open `plugin.json` and bump a number before every
    upload, and an author who forgot was told their changed controller
    was already imported. The number was doing no work — a candidate
    hashes on the archive's checksum — so it was a hand-maintained field
    whose only effect was to refuse real changes.
    """

    def upload(self, client, admin, planner: str, name: str = "Wall follower"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("wall_follower/.planbench-plugin/plugin.json", json.dumps(MANIFEST))
            archive.writestr("wall_follower/__init__.py", INIT_PY)
            archive.writestr("wall_follower/planner.py", planner)
        return client.post(
            "/api/v1/algorithms/plugins",
            data={
                "name": name,
                "version": "1",
                "robot_profile_id": default_profile(client, admin),
            },
            files={"bundle": ("wf.zip", io.BytesIO(buffer.getvalue()), "application/zip")},
            headers=admin,
        )

    def test_changed_code_is_accepted_without_touching_the_manifest(self, client, admin, imported):
        faster = PLANNER.replace("cruise_speed=0.35", "cruise_speed=0.75")
        assert faster != PLANNER
        response = self.upload(client, admin, faster)
        assert response.status_code == 201, response.text
        assert response.json()["plugin_version"] == MANIFEST["version"], "the label did not move"
        assert response.json()["revision"] == 2, "the platform counted the upload instead"

    def test_the_same_bytes_are_refused_and_the_message_says_why(self, client, admin, imported):
        response = self.upload(client, admin, PLANNER)
        assert response.status_code == 422
        assert "Nothing in it has changed" in response.json()["error"]["message"]

    def test_the_upload_it_replaces_is_retired(self, client, admin, imported):
        """Only one upload can be what the stack id resolves to, so
        leaving the others enabled shows a screen that disagrees with the
        platform. Disabled, never deleted: results recorded against the
        earlier upload still resolve to the bundle that produced them."""
        self.upload(client, admin, PLANNER.replace("cruise_speed=0.35", "cruise_speed=0.75"))
        rows = client.get("/api/v1/algorithms/plugins", headers=admin).json()
        by_revision = {row["revision"]: row["status"] for row in rows}
        assert by_revision == {1: "disabled", 2: "active"}

    def test_the_new_upload_is_the_one_that_runs(self, client, admin, imported):
        from planbench_benchmark.candidates import candidate_from_stack

        response = self.upload(
            client, admin, PLANNER.replace("cruise_speed=0.35", "cruise_speed=0.75")
        )
        candidate = candidate_from_stack(f"astar+{PLUGIN_ID}", params={})
        assert candidate.local_controller.version == response.json()["checksum"][:12]

    def test_the_two_uploads_do_not_share_a_directory(self, client, admin, imported, tmp_path):
        """Keyed on the checksum, because keying on the declared version
        put changed code on top of the code it replaced the moment an
        author forgot to bump it."""
        from planbench_api.plugin_registry import PluginBundleRecord
        from planbench_api.plugin_runtime import install_root

        first = PluginBundleRecord(id="a", name="x", plugin_id=PLUGIN_ID, checksum="a" * 64)
        second = PluginBundleRecord(id="b", name="x", plugin_id=PLUGIN_ID, checksum="b" * 64)
        assert install_root(tmp_path, first) != install_root(tmp_path, second)


class TestSomebodyElseCannotImportIt:
    def test_a_member_is_refused(self, client):
        assert do_import(client, auth_headers(client, ALICE)).status_code == 403
