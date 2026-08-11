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

from planbench_benchmark.task_map import load_task_map
from planbench_decision.card import CARD_SCHEMA_PATH, MANIFEST_SCHEMA_PATH
from planbench_metrics.definitions import compute_metrics
from planbench_schemas.episode_context import EpisodeContext
from planbench_simulator.trace import read_trace, trace_path

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
        "environment": {
            "map": "room.pgm",
            "map_yaml": "room.yaml",
            # Traffic the robot actually meets. Without it a deterministic
            # stack drives the identical episode on every seed, G2 counts
            # the set as one independent sample (HĐ-7.1) and refuses to
            # bound anything — the correct verdict, and one that leaves
            # the slice with nothing to card.
            #
            # Placement is deliberate and was measured, not guessed. The
            # straight run from (1.0, 1.0) to (4.8, 2.8) crosses x = 3.0
            # at y ~ 1.95, so a trolley patrolling *through* that point
            # blocks the only corridor and A* fails G3 outright — the
            # first two attempts here did exactly that. Patrolling from
            # y = 2.35 upward keeps it just outside the pair of radii
            # (0.15 + 0.15), so it perturbs clearance and near misses
            # without ever making the mission impossible. That is the
            # distinction the fixture needs: traffic that varies the
            # episode, not traffic that ends it.
            #
            # `seed_time_offset` covers a full period, so seeds meet it
            # at different points of its sweep.
            "dynamic_obstacles": [
                {
                    "name": "trolley",
                    "radius": 0.15,
                    "seed_time_offset": 9.0,
                    "motion": {
                        "kind": "periodic",
                        "start": {"x": 3.0, "y": 2.35},
                        "end": {"x": 3.0, "y": 3.4},
                        "period": 9.0,
                    },
                }
            ],
        },
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
def slice_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where this module's run put its files.

    Named separately from ``slice_result`` because the tests that read
    artefacts off disk need the directory, not the return value — and
    because they used to find it by globbing pytest's shared base temp,
    which quietly meant "the first ``traces`` directory any test module
    happened to create". That held until a second module wrote one, and
    then a rebuild test looked for the slice's episodes inside another
    module's trace root and found nothing.
    """
    return tmp_path_factory.mktemp("slice")


@pytest.fixture(scope="module")
def slice_result(slice_workspace: Path) -> dict[str, object]:
    """Run the whole slice once; every test below reads the same output."""
    workspace = slice_workspace
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
        self, slice_workspace: Path, slice_result: dict[str, object]
    ) -> None:
        """HĐ-13's manifest is half the deliverable, not a log line."""
        runs = list(slice_workspace.rglob("manifest.json"))
        assert runs, "no manifest was written"
        manifest = json.loads(runs[0].read_text(encoding="utf-8"))
        validator = Draft202012Validator(
            json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        )
        assert sorted(validator.iter_errors(manifest), key=str) == []
        assert manifest["bootstrap"] == {"seed": 3, "n_resamples": 1000}


class TestTheManifestCanActuallyRebuild:
    """HĐ-13's acceptance test, run rather than asserted about.

    "Hand somebody the manifest and they rebuild the same card" was
    stated from 1.0.0 and did not hold until 5.0.0: the manifest carried
    ``episode_context_ids``, and ``episode_context_id`` is a hash of the
    conditions (HĐ-3.1). Hashes do not invert, so a holder knew *which*
    episodes ran but had no mission and no seed to recompute a metric
    from — and HĐ-6 needs both.

    The gap was invisible in every run the project had made, because the
    slice builds the manifest and the metrics in one process where the
    ``EpisodeContext`` objects are still in memory. So this test throws
    them away: it reads the manifest and the traces off disk and
    recomputes, exactly as a stranger would.
    """

    def test_metrics_recompute_from_the_manifest_and_traces_alone(
        self, slice_workspace: Path, slice_result: dict[str, object]
    ) -> None:
        base = slice_workspace
        manifest = json.loads(next(base.rglob("manifest.json")).read_text(encoding="utf-8"))
        profile_path = next(base.rglob("profile.yaml"))
        profile = slice_module.load_profile(profile_path)
        map_data = load_task_map(profile, base_dir=profile_path.parent)

        contexts = [
            EpisodeContext.model_validate(record)
            for record in manifest["episode_contexts"]["evaluation"]
        ]
        assert contexts, "the manifest carried no conditions to rebuild from"

        candidate_id = manifest["candidates"][0]
        trace_root = next(base.rglob("traces"))
        rebuilt = 0
        for context in contexts:
            path = trace_path(candidate_id, context.episode_context_id, root=trace_root)
            if not path.is_file():
                continue
            metrics = compute_metrics(read_trace(path), profile, context, map_data)
            assert metrics.episode_context_id == context.episode_context_id
            assert metrics.path_length_m > 0.0
            rebuilt += 1
        assert rebuilt == len(contexts), "not every recorded episode could be recomputed"

    def test_the_records_carry_what_a_rebuild_needs(
        self, slice_workspace: Path, slice_result: dict[str, object]
    ) -> None:
        """Named separately from the rebuild so a regression says which
        half broke: the fields, or the recomputation."""
        base = slice_workspace
        manifest = json.loads(next(base.rglob("manifest.json")).read_text(encoding="utf-8"))
        for record in manifest["episode_contexts"]["evaluation"]:
            assert record["mission_id"]
            assert record["seed"] >= 0
            assert record["environment_variant"]
            assert record["sample_set"] == "evaluation"
            # And the id it hashes to, so a reader can find the trace file.
            assert (
                EpisodeContext.model_validate(record).episode_context_id
                == (record["episode_context_id"])
            )


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


class TestTheRunPlanInterleaves:
    """HĐ-3.2's loop order, asserted on the script rather than the helper.

    ``iter_run_plan`` has had this right since Phase 1.3, and ``simulate``
    quietly did not use it — it looped candidate-outer. At 30 episodes
    over ten minutes that was invisible. At 300 episodes over three hours
    it puts one candidate in the first half of the wall clock and the
    other in the second, so any thermal throttling or background process
    lands entirely on one of them. That is the exact mechanism that
    eliminated A* at G4 in the first Phase 4 run (contract 3.0.0), and
    HĐ-7.4 exists to forbid it.

    The second reason is interruption: stopped halfway, candidate-outer
    leaves one candidate with everything and the other with nothing.
    """

    def test_simulate_runs_context_outer_candidate_inner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asserted on ``simulate`` itself, over a full sweep.

        The simulator is stubbed out — what is under test is the order
        episodes are dispatched in, and running them for real would take
        a minute to observe something that is pure control flow.
        """
        profile_path = write_profile(tmp_path)
        profile = slice_module.load_profile(profile_path)
        map_data = load_task_map(profile, base_dir=tmp_path)
        candidates = slice_module.build_candidates()
        contexts = slice_module.build_evaluation_contexts(profile, seed_count=3)

        dispatched: list[tuple[str, int]] = []

        def record(candidate, _profile, context, _map_data, root):  # type: ignore[no-untyped-def]
            dispatched.append((candidate.candidate_id, context.seed))
            return None, _FakeRun()

        monkeypatch.setattr(slice_module, "run_contract_episode", record)
        slice_module.simulate(candidates, profile, contexts, map_data, tmp_path / "t", reuse=False)

        assert len(dispatched) == 6, "every (context, candidate) pair should be dispatched"
        # Seeds advance only after both candidates have run that seed.
        assert [seed for _, seed in dispatched] == [0, 0, 1, 1, 2, 2]
        # Consecutive episodes alternate candidates, which is what makes
        # them share the machine's condition minute by minute.
        first, second = candidates[0].candidate_id, candidates[1].candidate_id
        assert [cid for cid, _ in dispatched] == [first, second] * 3

    def test_a_run_that_dies_partway_still_paired(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A three-hour run can be killed. Under the old order that left
        one candidate with everything and the other with nothing; under
        this one both stop within an episode of each other."""
        profile_path = write_profile(tmp_path)
        profile = slice_module.load_profile(profile_path)
        map_data = load_task_map(profile, base_dir=tmp_path)
        candidates = slice_module.build_candidates()
        contexts = slice_module.build_evaluation_contexts(profile, seed_count=5)

        done: list[str] = []

        def die_after_seven(candidate, _profile, context, _map_data, root):  # type: ignore[no-untyped-def]
            if len(done) == 7:
                raise KeyboardInterrupt
            done.append(candidate.candidate_id)
            return None, _FakeRun()

        monkeypatch.setattr(slice_module, "run_contract_episode", die_after_seven)
        with pytest.raises(KeyboardInterrupt):
            slice_module.simulate(
                candidates, profile, contexts, map_data, tmp_path / "t", reuse=False
            )

        counts = {cid: done.count(cid) for cid in {c.candidate_id for c in candidates}}
        assert max(counts.values()) - min(counts.values()) <= 1, counts

    def test_an_interrupted_run_leaves_both_candidates_equal(self) -> None:
        """The property the order buys: stop anywhere and the two
        candidates differ by at most one episode, so what was collected
        is still a valid paired comparison."""
        profile = slice_module.load_profile(slice_module.PROFILE_PATH)
        candidates = slice_module.build_candidates()
        contexts = slice_module.build_evaluation_contexts(profile, seed_count=10)
        plan = list(slice_module.iter_run_plan(contexts, candidates))
        for cut in range(1, len(plan)):
            counts: dict[str, int] = {}
            for _, candidate in plan[:cut]:
                counts[candidate.candidate_id] = counts.get(candidate.candidate_id, 0) + 1
            assert max(counts.values()) - min(counts.values(), default=0) <= 1, (
                f"after {cut} episodes the candidates are unbalanced: {counts}"
            )


class _FakeRun:
    """Just enough of an episode result for ``simulate`` to print a line."""

    class result:  # noqa: N801 - mimics the real attribute path
        class status:  # noqa: N801
            value = "success"
