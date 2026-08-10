"""The vertical slice, end to end (CONTRACTS HĐ-15.1).

Every other test in the decision layer feeds fabricated traces to one
module. This one runs the real chain — simulator, Parquet trace, metrics,
gates, objectives, paired bootstrap, card — and checks that the six
acceptance criteria hold on data nobody hand-wrote. That is the whole
point of the slice: the modules already agree with their own
assumptions, and only a real run can show whether the assumptions are
true of the simulator.

It runs on a small open map rather than the shipped warehouse, for one
reason and with one cost. The reason is wall clock: the warehouse takes
about twenty seconds per episode and the slice needs sixty of them, which
is not a unit test. The cost is that this fixture cannot catch a problem
that only a cluttered map produces — so the warehouse run stays a
scripted command with its output committed under ``artifacts/runs/``,
and this test guards the plumbing against regressions.
"""

from __future__ import annotations

import importlib.util
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from planbench_decision.card import CARD_SCHEMA_PATH, MANIFEST_SCHEMA_PATH

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_slice_module():  # type: ignore[no-untyped-def]
    """Import ``scripts/vertical_slice.py``, which is not on the path."""
    spec = importlib.util.spec_from_file_location(
        "vertical_slice", REPO_ROOT / "scripts" / "vertical_slice.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


slice_module = _load_slice_module()


def write_open_map(directory: Path, *, width: int = 60, height: int = 40) -> tuple[Path, Path]:
    """A walled but otherwise empty 6×4 m room at 10 cm resolution.

    Free space with a solid border: the border is what keeps
    ``clearance_m`` finite everywhere (an empty map has no obstacle to
    measure against) and gives A\\* and RRT\\* something to route inside.
    """
    pixels = bytearray()
    for row in range(height):
        for col in range(width):
            edge = row in (0, height - 1) or col in (0, width - 1)
            pixels.append(0 if edge else 254)
    image = directory / "room.pgm"
    image.write_bytes(f"P5\n{width} {height}\n255\n".encode("ascii") + bytes(pixels))

    meta = directory / "room.yaml"
    meta.write_text(
        yaml.safe_dump(
            {
                "image": "room.pgm",
                "resolution": 0.1,
                "origin": [0.0, 0.0, 0.0],
                "negate": 0,
                "occupied_thresh": 0.65,
                "free_thresh": 0.196,
                "mode": "trinary",
            }
        ),
        encoding="utf-8",
    )
    return image, meta


def write_profile(directory: Path) -> Path:
    """A deployment small enough to gate on six episodes.

    ``collision_probability_max: 0.5`` makes ``N_min = ceil(3 / 0.5) = 6``
    (HĐ-7.1). That is a deployment which accepts a 50% collision risk —
    absurd for a warehouse and exactly right for a fixture, because it
    lets G2 pass honestly on six episodes instead of being switched off.
    """
    write_open_map(directory)
    payload = {
        "id": "slice_fixture_v1",
        "claim_level": "mission",
        "environment": {"map": "room.pgm", "map_yaml": "room.yaml"},
        "missions": [
            {"id": "m1", "start": [1.0, 1.0, 0.0], "goal": [4.8, 2.8, 0.0], "probability": 1.0}
        ],
        "robot": {
            "type": "differential_drive",
            "radius": 0.15,
            "max_linear_velocity": 0.8,
            "max_angular_velocity": 1.5,
            "max_linear_acceleration": 1.0,
            "max_angular_acceleration": 2.0,
            # 2 Hz. Absurd for a real robot and deliberate here: G4
            # compares the measured p99 against this, and on a shared CI
            # machine a Python control step occasionally takes 100 ms for
            # reasons that have nothing to do with the planner. A tight
            # budget would eliminate whichever candidate happened to run
            # during a garbage collection, and the test would fail at
            # random. The physics stays at MAX_SIMULATION_DT regardless.
            "control_period": 0.5,
        },
        "available_observations": ["lidar_2d"],
        "constraints": {
            "success_rate_min": 0.95,
            "collision_probability_max": 0.5,
            "no_path_rate_max": 0.02,
            "goal_tolerance_m": 0.20,
            # Wide on purpose — the simulator has no final-orientation
            # controller, so a heading requirement would fail every
            # candidate for a property of the platform. Same reservation
            # as the shipped profile.
            "goal_tolerance_rad": 3.1416,
            "episode_timeout_s": 40,
            "stuck_threshold_s": 8,
            "clearance_warning_m": 0.30,
        },
        "hardware": {
            "target_device": "jetson_orin_nano",
            "total_ram_mb": 8192,
            "ram_budget_breakdown": {
                "os_and_middleware_mb": 1536,
                "perception_stack_mb": 2048,
                "localization_mapping_mb": 819,
                "logging_and_reserve_mb": 512,
            },
            "available_ram_mb": 3277,
        },
    }
    path = directory / "profile.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def slice_result(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """Run the whole slice once; every test below reads the same output."""
    workspace = tmp_path_factory.mktemp("slice")
    profile_path = write_profile(workspace)
    return slice_module.run_slice(
        episodes=6,
        trace_root=workspace / "traces",
        run_root=workspace / "runs",
        reuse=False,
        bootstrap_seed=3,
        git_sha="0123456789abcdef0123456789abcdef01234567",
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        profile_path=profile_path,
        map_base_dir=workspace,
        quiet=True,
    )


class TestItRunsAtAll:
    def test_the_chain_produces_a_card(self, slice_result: dict[str, object]) -> None:
        """Trace → metrics → gates → objectives → ΔU → card, on real
        episodes. If any link were broken this would not return."""
        assert slice_result["status"] in {"CLEAR_RECOMMENDATION", "NEAR_EQUIVALENT"}
        assert slice_result["recommended"]["candidate_id"]  # type: ignore[index]

    def test_the_card_validates_against_the_contract_schema(
        self, slice_result: dict[str, object]
    ) -> None:
        validator = Draft202012Validator(json.loads(CARD_SCHEMA_PATH.read_text(encoding="utf-8")))
        assert sorted(validator.iter_errors(slice_result), key=str) == []

    def test_both_artefacts_land_on_disk(
        self, tmp_path_factory: pytest.TempPathFactory, slice_result: dict[str, object]
    ) -> None:
        """HĐ-13's manifest is half the deliverable, not a log line."""
        runs = list(Path(tmp_path_factory.getbasetemp()).rglob("manifest.json"))
        assert runs, "no manifest was written"
        manifest = json.loads(runs[0].read_text(encoding="utf-8"))
        validator = Draft202012Validator(
            json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        )
        assert sorted(validator.iter_errors(manifest), key=str) == []
        assert manifest["bootstrap"] == {"seed": 3, "n_resamples": 1000}


class TestAcceptanceCriteria:
    """HĐ-15.1's six checks, asserted on the produced card.

    ``run_slice`` already raises :class:`SliceFailure` if any of them
    fails, so these are deliberately checking the *evidence on the card*
    rather than re-running the checkers — a criterion that holds inside
    the script but leaves no trace in the output would be worthless to
    the person reading the card.
    """

    def test_three_all_six_gates_with_their_run_count(
        self, slice_result: dict[str, object]
    ) -> None:
        gates = slice_result["gates"]  # type: ignore[index]
        assert len(gates) == 2
        for row in gates:
            assert {"G1", "G2", "G3", "G4", "G5", "G6"} <= set(row)
            assert row["G2"]["n_runs"] == 6
            assert row["G2"]["n_min"] == 6

    def test_four_delta_u_and_its_ci_are_real_numbers(
        self, slice_result: dict[str, object]
    ) -> None:
        evidence = slice_result["evidence"]  # type: ignore[index]
        low, high = evidence["ci95"]
        assert math.isfinite(evidence["delta_u_vs_second"])
        assert math.isfinite(low) and math.isfinite(high)
        assert low <= high
        assert evidence["n_episodes"] == 6

    def test_the_g2_statement_quotes_the_bound_for_six_runs(
        self, slice_result: dict[str, object]
    ) -> None:
        """HĐ-7.1's sentence, with the number this run actually supports:
        zero collisions in six runs bounds the rate at 50%, not at zero.
        """
        for row in slice_result["gates"]:  # type: ignore[index]
            if row["G2"]["observed"] == 0:
                assert "6 lần chạy" in row["G2"]["statement"]
                assert row["G2"]["upper_bound_95"] == pytest.approx(0.5)

    def test_the_recommendation_cleared_every_gate(self, slice_result: dict[str, object]) -> None:
        """Criterion 3 has a corollary the card must show: the winner is
        a candidate with six passing gates, not the best score."""
        winner = slice_result["recommended"]["candidate_id"]  # type: ignore[index]
        row = next(r for r in slice_result["gates"] if r["candidate_id"] == winner)  # type: ignore[index]
        assert row["G1"] == "pass" and row["G3"] == "pass" and row["G6"] == "pass"
        assert row["G2"]["result"] == "pass"
        assert row["G4"]["result"] == "pass"
        assert row["G5"]["result"] == "pass"


class TestWhatTheSliceRefuses:
    def test_a_broken_l_ref_is_caught(self) -> None:
        """Criterion 5 exists to catch a reference path longer than the
        route actually driven — the symptom of a wrong Dijkstra or a
        wrong odometer, both of which feed path_efficiency."""

        class Row:
            success = True
            l_ref_m = 12.0
            path_length_m = 9.0
            episode_context_id = "ctx"
            peak_search_nodes = 1
            costmap_cells = 10

        with pytest.raises(slice_module.SliceFailure, match="exceeds the driven path"):
            slice_module.check_l_ref({"cand": [Row()]}, 0.2)

    def test_the_goal_tolerance_slack_is_allowed(self) -> None:
        """The other side of the same check. A robot that stops at the
        edge of the tolerance ball drove less than the distance to the
        goal centre, and that is not an error (HĐ-15.1(5) at 2.2.1)."""

        class Row:
            success = True
            l_ref_m = 4.205
            path_length_m = 4.024
            episode_context_id = "ctx"

        assert slice_module.check_l_ref({"cand": [Row()]}, 0.20)

    def test_node_counts_over_the_grid_are_caught(self) -> None:
        class Row:
            success = True
            l_ref_m = 1.0
            path_length_m = 2.0
            episode_context_id = "ctx"
            peak_search_nodes = 999
            costmap_cells = 10

        with pytest.raises(slice_module.SliceFailure, match="search nodes over"):
            slice_module.check_node_counts({"cand": [Row()]})

    def test_unshared_contexts_are_caught(self) -> None:
        class Row:
            def __init__(self, context_id: str) -> None:
                self.episode_context_id = context_id

        with pytest.raises(slice_module.SliceFailure, match="different context set"):
            slice_module.check_shared_contexts({"a": [Row("x")], "b": [Row("y")]})

    def test_an_irreproducible_utility_is_caught(self) -> None:
        with pytest.raises(slice_module.SliceFailure, match="not reproducible"):
            slice_module.check_reproducible(0.1234561, 0.1234573)


class TestExperimentScope:
    def test_the_two_candidates_hold_the_controller_fixed(self) -> None:
        """HĐ-1.4: the slice claims something about global planners, so
        the local controller and its parameters must be identical in both
        — otherwise the conclusion covers a change nobody isolated.
        ``build_candidates`` validates this and raises if it ever stops
        being true; this test is here so the reason is written down.
        """
        candidates = slice_module.build_candidates()
        assert len(candidates) == 2
        assert {c.global_planner.name for c in candidates} == {"astar", "rrtstar"}
        assert len({c.local_controller.name for c in candidates}) == 1
        assert len({json.dumps(c.layer_params("dwa"), sort_keys=True) for c in candidates}) == 1
