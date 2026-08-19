"""E4.5 — the planning-input sidecar, written as the episode happens.

What these guard: every planning attempt gets a record including the
ones that found nothing; the grid recorded is the one the planner was
handed and not the map on disk; a writer that stops early is caught by
the runner's own counter rather than by its own; and a replay of a
recorded attempt reaches ``mechanism_verified`` where a replay of an
unrecorded one cannot.
"""

from __future__ import annotations

import json

import pytest
from blocked_route import blocked_robot, two_doorway_map
from blocked_route import blocked_scenario as build_blocked_scenario

from planbench_explanation.planning_input_evidence import (
    PlanningInputEvidence,
    PlanningQuery,
    ReplayObservation,
    SidecarViolation,
    admit_replay_with_sidecar,
    admit_replay_without_sidecar,
    validate_episode_attempts,
)
from planbench_explanation.sidecar_writer import (
    SIDECAR_FILENAME,
    GridSnapshot,
    PlanningInputRecorder,
    SidecarHeader,
    costmap_checksum,
    planner_fingerprint,
    read_sidecar,
    replay_inputs,
    snapshot_for,
    write_sidecar,
)
from planbench_planning import AStarPlanner, DWAPlanner
from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.replanning import ReplanningConfig
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import run_stack

BUILD = "git:" + "c" * 40


def grid(blocked_column: int = 2) -> GridSnapshot:
    """A 4x4 world with one column of obstacles. Small and real."""
    cells = [1 if col == blocked_column else 0 for _row in range(4) for col in range(4)]
    return GridSnapshot(
        width=4, height=4, resolution=0.5, origin_x=0.0, origin_y=0.0, cells=tuple(cells)
    )


FINGERPRINT = planner_fingerprint("astar", {"heuristic": "euclidean", "tie_break": 1.001})


@pytest.fixture
def robot() -> RobotConfig:
    return blocked_robot()


@pytest.fixture
def blocked(robot: RobotConfig) -> Scenario:
    return build_blocked_scenario(robot)


def recorder(**overrides) -> PlanningInputRecorder:  # type: ignore[no-untyped-def]
    fields = {
        "run_id": "run_017",
        "episode_context_id": "ep-004",
        "candidate_id": "astar+dwa",
        "execution_environment_ref": BUILD,
    }
    fields.update(overrides)
    return PlanningInputRecorder(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The writer, on a real episode
# --------------------------------------------------------------------------


def test_a_replanning_episode_records_every_attempt(blocked: Scenario) -> None:
    """Initial plan plus one record per replan, from the real loop."""
    writing = recorder()
    run = run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        None,
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=writing,
    )
    expected = (run.metrics.replan_count or 0) + 1
    records = writing.close(expected_attempts=expected)

    assert len(records) == expected
    assert [record.planning_attempt for record in records] == list(range(1, expected + 1))
    assert all(record.candidate_id == "astar+dwa" for record in records)


class RefusesAfterTheFirst(GlobalPlanner):
    """Plans once, then refuses — the shape the sidecar exists for.

    Scripted rather than found: on the two-doorway map the replan
    succeeds through the other doorway, so an episode there would leave
    the no-path branch untested and the assertion would pass by not
    being exercised.
    """

    def __init__(self) -> None:
        self._inner = AStarPlanner()
        self.calls = 0

    @property
    def name(self) -> str:
        return "refuses-after-the-first"

    def plan(self, grid, start: Point2D, goal: Point2D) -> PlanResult:  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls == 1:
            return self._inner.plan(grid, start, goal)
        return PlanResult(success=False, failure_reason="no_global_path")


def test_the_attempt_that_found_nothing_is_recorded_too(blocked: Scenario) -> None:
    """``StackRun.plans`` keeps the successes; the sidecar keeps the rest.

    The episode somebody most wants explained is the one where the
    planner returned no path, and before this writer that attempt left
    nothing behind at all — ``StackRun.plans`` has no row for it.
    """
    writing = recorder()
    planner = RefusesAfterTheFirst()
    run = run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        planner,
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=writing,
    )
    writing.close(expected_attempts=(run.metrics.replan_count or 0) + 1)

    outcomes = [record.outcome for record in writing.records]
    assert outcomes[0] == "path"
    assert "no_path" in outcomes

    failed = next(record for record in writing.records if record.outcome == "no_path")
    assert failed.failure_code == "no_global_path"
    assert failed.output_plan_checksum is None

    # The point of the whole wave, in one assertion: the refusal is in
    # the sidecar and it is not in the run's own record of its plans.
    assert len(run.plans) < len(writing.records)


def test_two_attempts_in_one_episode_see_different_grids(blocked: Scenario) -> None:
    """The costmap hashed is the one handed over, not the map on disk.

    A replan plans on what the robot now believes, with standing room
    relaxed around it. Hashing the source map would make every attempt
    look identical, which would make a replay look reproducible when it
    is not.
    """
    writing = recorder()
    run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        None,
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=writing,
    )
    checksums = {record.costmap_checksum for record in writing.records}
    assert len(writing.records) >= 2
    assert len(checksums) >= 2


def test_a_run_without_a_recorder_behaves_exactly_as_before(blocked: Scenario) -> None:
    """The seam is optional, like the trace recorder's."""
    with_writer = recorder()
    a = run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        None,
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=with_writer,
    )
    b = run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        None,
        ReplanningConfig(enabled=True, max_replans=3),
    )
    assert a.result.status is b.result.status
    assert a.metrics.replan_count == b.metrics.replan_count
    assert a.result.elapsed_time == pytest.approx(b.result.elapsed_time)


# --------------------------------------------------------------------------
# The counter that catches a writer stopping early
# --------------------------------------------------------------------------


def attempt(number: int, **overrides) -> PlanningInputEvidence:  # type: ignore[no-untyped-def]
    fields = {
        "episode_context_id": "ep-004",
        "candidate_id": "astar+dwa",
        "planning_attempt": number,
        "simulation_tick": number * 10,
        "query": PlanningQuery(
            start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
            goal_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
        ),
        "costmap_checksum": f"grid-{number}",
        "snapshot_ref": f"snapshots/attempt-{number:03d}.json",
        "snapshot_checksum": f"{number:064d}",
        "planner_fingerprint": FINGERPRINT,
        "execution_environment_ref": BUILD,
        "outcome": "path",
        "output_plan_checksum": f"plan-{number}",
    }
    fields.update(overrides)
    return PlanningInputEvidence(**fields)  # type: ignore[arg-type]


def test_a_truncated_tail_is_caught_by_the_runners_count() -> None:
    """``[1]`` is perfectly contiguous and perfectly wrong."""
    with pytest.raises(SidecarViolation, match="missing tail|expected"):
        validate_episode_attempts([attempt(1)], expected_attempts=3)


def test_the_recorder_will_not_supply_its_own_expectation() -> None:
    """A validator fed its own input can only ever agree with it."""
    writing = recorder()
    writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
        grid=grid(),
        planner_name="AStarPlanner",
        outcome="path",
        output_plan_checksum="plan-1",
    )
    assert writing.attempts == 1
    with pytest.raises(SidecarViolation):
        writing.close(expected_attempts=2)


def test_an_attempt_after_the_episode_ended_belongs_to_another_episode() -> None:
    writing = recorder()
    writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
        grid=grid(),
        planner_name="AStarPlanner",
        outcome="path",
        output_plan_checksum="plan-1",
    )
    writing.close(expected_attempts=1)
    with pytest.raises(SidecarViolation, match="closed"):
        writing.record(
            simulation_tick=1,
            start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
            goal_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
            grid=grid(3),
            planner_name="AStarPlanner",
            outcome="no_path",
            failure_code="no_global_path",
        )


def test_a_failed_episode_leaves_its_partial_sidecar_unvalidated() -> None:
    """Validating here would turn one failure into two and hide the first."""
    writing = recorder()
    writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
        grid=grid(),
        planner_name="AStarPlanner",
        outcome="path",
        output_plan_checksum="plan-1",
    )
    writing.abandon()
    assert writing.attempts == 1


# --------------------------------------------------------------------------
# The file
# --------------------------------------------------------------------------


def test_a_sidecar_round_trips(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / SIDECAR_FILENAME
    header = SidecarHeader(
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="astar+dwa",
        execution_environment_ref=BUILD,
    )
    write_sidecar(
        path,
        header,
        [
            attempt(1),
            attempt(2, outcome="no_path", output_plan_checksum=None, failure_code="no_global_path"),
        ],
    )
    read_header, records = read_sidecar(path)
    assert read_header == header
    assert [record.planning_attempt for record in records] == [1, 2]
    assert records[1].failure_code == "no_global_path"


def test_the_recorder_writes_as_it_goes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A run that raises halfway leaves what it collected."""
    path = tmp_path / SIDECAR_FILENAME
    writing = PlanningInputRecorder.to_path(
        path,
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="astar+dwa",
        execution_environment_ref=BUILD,
    )
    writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
        grid=grid(),
        planner_name="AStarPlanner",
        outcome="path",
        output_plan_checksum="plan-1",
    )
    # Nothing closed, nothing flushed at the end: the line is on disk.
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["kind"] == "planning_input_sidecar"
    writing.abandon()


def test_a_headerless_file_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A replay would read the resulting mismatch as a failed reconstruction."""
    path = tmp_path / SIDECAR_FILENAME
    path.write_text(json.dumps(attempt(1).model_dump(mode="json")) + "\n", encoding="utf-8")
    with pytest.raises(SidecarViolation, match="header"):
        read_sidecar(path)


def test_a_record_from_another_episode_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / SIDECAR_FILENAME
    header = SidecarHeader(
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="astar+dwa",
        execution_environment_ref=BUILD,
    )
    write_sidecar(path, header, [attempt(1, episode_context_id="ep-009")])
    with pytest.raises(SidecarViolation, match="under a header for"):
        read_sidecar(path)


def test_a_grid_checksum_is_about_the_grid_not_the_cells_alone() -> None:
    """Same cells at a different resolution is a different world."""
    cells = [0, 1, 0, 1]
    assert costmap_checksum(cells, width=2, height=2, resolution=0.05) != costmap_checksum(
        cells, width=2, height=2, resolution=0.10
    )
    assert costmap_checksum(cells, width=2, height=2, resolution=0.05) == costmap_checksum(
        cells, width=2, height=2, resolution=0.05
    )


def test_a_planner_fingerprint_is_about_the_knobs_too() -> None:
    """A replay that reproduces a path at a different budget reproduced nothing."""
    assert planner_fingerprint("rrtstar", {"samples": 1000}) != planner_fingerprint(
        "rrtstar", {"samples": 4000}
    )
    assert planner_fingerprint("rrtstar", {"a": 1, "b": 2}) == planner_fingerprint(
        "rrtstar", {"b": 2, "a": 1}
    )


def test_the_fingerprint_is_derived_from_the_snapshot_not_supplied() -> None:
    """A caller could otherwise file planner A's hash beside planner B's knobs."""
    writing = recorder()
    record = writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=1.5, y=1.5, theta=0.0),
        grid=grid(),
        planner_name="rrtstar",
        planner_parameters={"max_iterations": 3000},
        seed=7,
        outcome="path",
        output_plan_checksum="plan-1",
    )
    assert record.planner_fingerprint == planner_fingerprint("rrtstar", {"max_iterations": 3000})


# --------------------------------------------------------------------------
# What the sidecar unblocks
# --------------------------------------------------------------------------


def test_a_recorded_attempt_can_reach_mechanism_verified() -> None:
    """The whole point: the ceiling a replay could not reach before."""
    recorded = attempt(1)
    replayed = ReplayObservation(
        costmap_checksum=recorded.costmap_checksum,
        query=recorded.query,
        planner_fingerprint=recorded.planner_fingerprint,
        execution_environment_ref=recorded.execution_environment_ref,
        outcome=recorded.outcome,
        output_plan_checksum=recorded.output_plan_checksum,
        failure_code=recorded.failure_code,
    )
    admission = admit_replay_with_sidecar(recorded, replayed, inputs_loaded_from_record=True)
    assert admission.input_provenance == "recorded"
    assert admission.maximum_supported_level == "mechanism_verified"


def test_the_same_replay_without_the_sidecar_stays_at_associated() -> None:
    """Unchanged, and it is the contrast that makes the writer worth writing."""
    admission = admit_replay_without_sidecar(
        ReplayObservation(
            costmap_checksum="rebuilt",
            query=PlanningQuery(
                start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
                goal_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
            ),
            planner_fingerprint=FINGERPRINT,
            execution_environment_ref=BUILD,
            outcome="path",
            output_plan_checksum="plan-1",
        ),
        recorded_output_plan_checksum="plan-1",
        plans_recorded=True,
    )
    assert admission.input_provenance == "reconstructed"
    assert admission.maximum_supported_level == "associated"


def test_a_replay_of_a_refusal_must_refuse_for_the_same_reason() -> None:
    """ "no path" and "timed out" are both no_path and different mechanisms."""
    recorded = attempt(
        2, outcome="no_path", output_plan_checksum=None, failure_code="no_global_path"
    )
    replayed = ReplayObservation(
        costmap_checksum=recorded.costmap_checksum,
        query=recorded.query,
        planner_fingerprint=recorded.planner_fingerprint,
        execution_environment_ref=recorded.execution_environment_ref,
        outcome="no_path",
        failure_code="planner_timeout",
    )
    admission = admit_replay_with_sidecar(recorded, replayed, inputs_loaded_from_record=True)
    assert admission.execution_status == "not_checkable"
    assert "mismatch:failure_code" in admission.reasons


# --------------------------------------------------------------------------
# A checksum cannot be replayed from — a snapshot can
# --------------------------------------------------------------------------


def test_every_record_points_at_a_snapshot_that_loads(tmp_path, blocked: Scenario) -> None:  # type: ignore[no-untyped-def]
    """The finding this wave was reopened for.

    A checksum verifies a grid somebody already has; it cannot produce
    one. The first cut stored only the hash, and the tests passed
    because they built the replay's inputs by copying the record.
    """
    path = tmp_path / SIDECAR_FILENAME
    writing = PlanningInputRecorder.to_path(
        path,
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="astar+dwa",
        execution_environment_ref=BUILD,
    )
    run = run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        None,
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=writing,
    )
    records = writing.close(expected_attempts=(run.metrics.replan_count or 0) + 1)

    for record in records:
        snapshot = snapshot_for(path, record)
        assert snapshot.grid.checksum == record.costmap_checksum
        assert len(snapshot.grid.cells) == snapshot.grid.width * snapshot.grid.height
        assert snapshot.planner_name


def test_a_recorded_attempt_can_actually_be_planned_again(tmp_path, blocked: Scenario) -> None:  # type: ignore[no-untyped-def]
    """Re-run the planner from the snapshot and get the same path.

    This is the assertion the admission tests could not make: they built
    the replay's inputs from the record's own fields, so they proved the
    scoring rules and not that anything could be replayed.
    """
    from planbench_schemas.geometry import Pose2D as SchemaPose
    from planbench_schemas.map import MapData
    from planbench_simulator.grid import OccupancyGrid
    from planbench_simulator.nav_stack import _plan_checksum

    path = tmp_path / SIDECAR_FILENAME
    writing = PlanningInputRecorder.to_path(
        path,
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="astar+dwa",
        execution_environment_ref=BUILD,
    )
    run = run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        None,
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=writing,
    )
    records = writing.close(expected_attempts=(run.metrics.replan_count or 0) + 1)
    first = records[0]

    inputs = replay_inputs(snapshot_for(path, first))
    rebuilt = OccupancyGrid(
        MapData(
            name="replay",
            width=inputs["width"],
            height=inputs["height"],
            resolution=inputs["resolution"],
            origin=SchemaPose(x=inputs["origin"][0], y=inputs["origin"][1], theta=0.0),
            cells=tuple(inputs["cells"]),
        )
    )
    replayed = AStarPlanner().plan(
        rebuilt,
        Point2D(x=inputs["start"][0], y=inputs["start"][1]),
        Point2D(x=inputs["goal"][0], y=inputs["goal"][1]),
    )
    assert replayed.success is (first.outcome == "path")
    assert _plan_checksum(replayed) == first.output_plan_checksum


def test_a_snapshot_that_drifted_from_its_sidecar_is_caught(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Otherwise a replay reads it as a failed reconstruction.

    "These two files do not belong together" and "the reconstruction is
    wrong" are different problems, and only one of them is about the
    run being explained.
    """
    path = tmp_path / SIDECAR_FILENAME
    writing = PlanningInputRecorder.to_path(
        path,
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="astar+dwa",
        execution_environment_ref=BUILD,
    )
    record = writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=1.5, y=1.5, theta=0.0),
        grid=grid(),
        planner_name="AStarPlanner",
        outcome="path",
        output_plan_checksum="plan-1",
    )
    stored = writing.snapshots[1]
    writing.abandon()
    assert snapshot_for(path, record).grid.checksum == record.costmap_checksum

    # Somebody replaced the snapshot with a different world.
    drifted = stored.model_copy(update={"grid": grid(3)})
    (tmp_path / "snapshots" / "attempt-001.json").write_text(
        drifted.model_dump_json(), encoding="utf-8"
    )
    with pytest.raises(SidecarViolation, match="hashes to"):
        snapshot_for(path, record)


def test_a_sampling_planners_seed_is_recorded_or_said_to_be_missing() -> None:
    """``None`` is a statement: replaying RRT* without its seed is a different tree."""
    writing = recorder()
    with_seed = writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=1.5, y=1.5, theta=0.0),
        grid=grid(),
        planner_name="RRTStarPlanner",
        planner_parameters={"samples": 2000},
        seed=17,
        outcome="path",
        output_plan_checksum="plan-1",
    )
    snapshot = writing.snapshots[with_seed.planning_attempt]
    assert snapshot.seed == 17
    assert snapshot.planner_parameters == {"samples": 2000}


def test_the_grids_origin_is_part_of_its_identity() -> None:
    """Same cells at a different origin is a different world.

    The origin turns a cell index into a world coordinate, so a start
    and goal replayed against the wrong one land somewhere else.
    """
    cells = (0, 1, 0, 1)
    assert costmap_checksum(
        cells, width=2, height=2, resolution=0.5, origin_x=0.0, origin_y=0.0
    ) != costmap_checksum(cells, width=2, height=2, resolution=0.5, origin_x=3.0, origin_y=0.0)


def test_a_snapshot_with_a_swapped_goal_is_caught_by_the_whole_hash(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The grid checksum alone let this through: right world, other question.

    Same cells, same attempt number — and a goal three metres away. A
    replay would have loaded it, planned somewhere else, and reported a
    mismatch as though the run were irreproducible.
    """
    path = tmp_path / SIDECAR_FILENAME
    writing = PlanningInputRecorder.to_path(
        path,
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="astar+dwa",
        execution_environment_ref=BUILD,
    )
    record = writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=1.5, y=1.5, theta=0.0),
        grid=grid(),
        planner_name="astar",
        outcome="path",
        output_plan_checksum="plan-1",
    )
    stored = writing.snapshots[1]
    writing.abandon()

    moved = stored.model_copy(update={"goal_x": 4.5})
    assert moved.grid.checksum == record.costmap_checksum  # the grid is untouched
    (tmp_path / "snapshots" / "attempt-001.json").write_text(
        moved.model_dump_json(), encoding="utf-8"
    )
    with pytest.raises(SidecarViolation, match="hashes to"):
        snapshot_for(path, record)


def test_a_snapshot_with_swapped_planner_parameters_is_caught_too(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Right grid, right query, a planner tuned differently."""
    path = tmp_path / SIDECAR_FILENAME
    writing = PlanningInputRecorder.to_path(
        path,
        run_id="run_017",
        episode_context_id="ep-004",
        candidate_id="rrtstar+dwa",
        execution_environment_ref=BUILD,
    )
    record = writing.record(
        simulation_tick=0,
        start_pose=Pose2D(x=0.0, y=0.0, theta=0.0),
        goal_pose=Pose2D(x=1.5, y=1.5, theta=0.0),
        grid=grid(),
        planner_name="rrtstar",
        planner_parameters={"max_iterations": 3000},
        seed=1,
        outcome="path",
        output_plan_checksum="plan-1",
    )
    retuned = writing.snapshots[1].model_copy(
        update={"planner_parameters": {"max_iterations": 12000}}
    )
    writing.abandon()
    (tmp_path / "snapshots" / "attempt-001.json").write_text(
        retuned.model_dump_json(), encoding="utf-8"
    )
    with pytest.raises(SidecarViolation, match="hashes to"):
        snapshot_for(path, record)


def test_the_runner_records_the_planners_actual_configuration(blocked: Scenario) -> None:
    """Not just its name.

    Every snapshot this runner produced carried empty parameters and no
    seed, so a replay of a tuned A* would have run the default.
    """
    from planbench_planning import AStarConfig
    from planbench_planning import AStarPlanner as Astar

    writing = recorder()
    run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        Astar(AStarConfig(connectivity=4)),
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=writing,
    )
    snapshot = writing.snapshots[1]
    assert snapshot.planner_name == "astar"
    assert snapshot.planner_parameters["connectivity"] == 4


def test_the_runner_records_a_sampling_planners_seed(blocked: Scenario) -> None:
    """``None`` here would mean a replay grows a different tree."""
    from planbench_planning import RRTStarConfig, RRTStarPlanner

    writing = recorder()
    run_stack(
        two_doorway_map(),
        blocked,
        DWAPlanner(),
        RRTStarPlanner(RRTStarConfig(max_iterations=800), episode_seed=17),
        ReplanningConfig(enabled=True, max_replans=1),
        planning_recorder=writing,
    )
    snapshot = writing.snapshots[1]
    assert snapshot.planner_name == "rrtstar"
    assert snapshot.seed == 17
    assert snapshot.planner_parameters["max_iterations"] == 800
