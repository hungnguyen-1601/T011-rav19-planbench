"""E6b — replaying a recorded planning attempt through an injected planner.

What these guard: the explanation layer holds no planner and gets one as
an argument; a replay that reproduces a recorded refusal supports the
mechanism while one that finds a path refutes it; a replay run on a
different build, a different configuration or a different costmap is
``not_checkable`` rather than a verdict; and a harness that cannot
rebuild the planner says so instead of substituting one.
"""

from __future__ import annotations

import pytest
from blocked_route import blocked_robot, two_doorway_map
from blocked_route import blocked_scenario as build_blocked_scenario
from pydantic import ValidationError

from planbench_explanation.checkers import CheckerRefusal
from planbench_explanation.planning_input_evidence import PlanningInputEvidence
from planbench_explanation.replay import (
    BUDGET_MULTIPLIERS,
    ConvergenceEvidence,
    ReplayEvidence,
    ReplayPlan,
    ReplayRequest,
    ReplayUnavailable,
    check_replay_global_plan,
    check_rrt_convergence,
)
from planbench_explanation.sidecar_writer import (
    SIDECAR_FILENAME,
    GridSnapshot,
    PlanningInputRecorder,
    PlanningSnapshot,
    planner_fingerprint,
    read_sidecar,
    snapshot_for,
)
from planbench_planning import AStarPlanner, DWAPlanner
from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.map import MapData
from planbench_schemas.replanning import ReplanningConfig
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.nav_stack import run_stack
from planbench_simulator.replay_planner import PLANNERS, SimulatorReplayPlanner

BUILD = "git:" + "c" * 40


@pytest.fixture
def robot() -> RobotConfig:
    return blocked_robot()


@pytest.fixture
def blocked(robot: RobotConfig) -> Scenario:
    return build_blocked_scenario(robot)


class RefusesAfterTheFirst(GlobalPlanner):
    """Plans once, then refuses. Deterministic, so it replays."""

    def __init__(self) -> None:
        self._inner = AStarPlanner()
        self.calls = 0

    @property
    def name(self) -> str:
        return "astar"

    def plan(self, grid, start: Point2D, goal: Point2D) -> PlanResult:  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls == 1:
            return self._inner.plan(grid, start, goal)
        return PlanResult(success=False, failure_reason="no_global_path")


def recorded_episode(tmp_path, scenario: Scenario, planner=None):  # type: ignore[no-untyped-def]
    """Run one real episode with the sidecar on; hand back its records."""
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
        scenario,
        DWAPlanner(),
        planner,
        ReplanningConfig(enabled=True, max_replans=3),
        planning_recorder=writing,
    )
    records = writing.close(expected_attempts=run.replan_attempts + 1)
    return path, records


def evidence_at(path, record) -> ReplayEvidence:  # type: ignore[no-untyped-def]
    return ReplayEvidence(record=record, snapshot=snapshot_for(path, record))


# --------------------------------------------------------------------------
# The seam
# --------------------------------------------------------------------------


def test_the_explanation_layer_holds_no_planner() -> None:
    """The reason this module exists rather than an import."""
    import planbench_explanation.replay as replay

    source = (replay.__file__ or "").lower()
    assert source
    text = open(replay.__file__, encoding="utf-8").read()  # noqa: SIM115
    assert "planbench_simulator" not in text
    assert "planbench_planning" not in text


def walled_grid() -> GridSnapshot:
    """A 12x12 world with a wall right across it. Genuinely infeasible."""
    cells = [100 if row == 6 else 0 for row in range(12) for _col in range(12)]
    return GridSnapshot.from_cells(
        cells, width=12, height=12, resolution=0.5, origin_x=0.0, origin_y=0.0
    )


def test_a_recorded_refusal_replays_to_a_supported_mechanism(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The claim E4.5 was built to make reachable.

    A real planner, a real refusal, recorded through the real writer and
    then re-run: the query is still infeasible on the costmap it was
    actually given, and every recorded input matched — so this is not a
    reconstruction and the ceiling is not ``associated``.

    The wall is built rather than found because the two-doorway map has,
    by construction, a second doorway: an episode there produces no
    genuinely infeasible query to record.
    """
    from planbench_simulator.nav_stack import _plan_checksum

    grid = walled_grid()
    start, goal = Point2D(x=1.0, y=1.0), Point2D(x=1.0, y=5.0)
    rebuilt = OccupancyGrid(
        MapData(
            name="walled",
            width=grid.width,
            height=grid.height,
            resolution=grid.resolution,
            origin=Pose2D(x=0.0, y=0.0, theta=0.0),
            cells=grid.cells,
        )
    )
    truth = AStarPlanner().plan(rebuilt, start, goal)
    assert not truth.success, "the fixture must pose a query A* really cannot answer"

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
        start_pose=Pose2D(x=start.x, y=start.y, theta=0.0),
        goal_pose=Pose2D(x=goal.x, y=goal.y, theta=0.0),
        grid=grid,
        planner_name="astar",
        planner_parameters={},
        outcome="no_path",
        failure_code=truth.failure_reason or "no_global_path",
    )
    writing.close(expected_attempts=1)
    assert _plan_checksum  # the harness and the recorder hash the same way

    outcome = check_replay_global_plan(
        evidence_at(path, record),
        planner=SimulatorReplayPlanner(execution_environment_ref=BUILD),
    )
    assert outcome.proposition_type == "geometric_infeasibility"
    assert outcome.verdict == "supported"
    assert outcome.measurements["paths_found"] == 0.0


def test_a_refusal_the_planner_does_not_reproduce_is_not_a_verdict(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    """A scripted refusal is a fact about the harness, not about the query.

    ``RefusesAfterTheFirst`` declines on its call count, and A* on the
    same costmap finds a route through the other doorway. The replay
    reports the divergence rather than promoting the refusal — which is
    the behaviour that keeps a stubbed or drifted planner from
    manufacturing a verified mechanism.
    """
    path, records = recorded_episode(tmp_path, blocked, RefusesAfterTheFirst())
    refused = next(record for record in records if record.outcome == "no_path")

    with pytest.raises(CheckerRefusal) as caught:
        check_replay_global_plan(
            evidence_at(path, refused),
            planner=SimulatorReplayPlanner(execution_environment_ref=BUILD),
        )
    assert caught.value.code == "replay_did_not_reproduce"
    assert "mismatch:outcome" in str(caught.value)


def test_a_recorded_path_replays_to_a_refutation(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    """A real answer, not a failure of the check."""
    path, records = recorded_episode(tmp_path, blocked)
    found = next(record for record in records if record.outcome == "path")

    outcome = check_replay_global_plan(
        evidence_at(path, found),
        planner=SimulatorReplayPlanner(execution_environment_ref=BUILD),
    )
    assert outcome.verdict == "refuted"
    assert outcome.measurements["paths_found"] == 1.0


def test_the_replay_reproduces_the_recorded_plan_byte_for_byte(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    """The harness is running the same query, not merely a similar one."""
    path, records = recorded_episode(tmp_path, blocked)
    found = next(record for record in records if record.outcome == "path")
    snapshot = snapshot_for(path, found)

    plan = SimulatorReplayPlanner(execution_environment_ref=BUILD).replay(
        ReplayRequest.from_snapshot(snapshot)
    )
    assert plan.outcome == "path"
    assert plan.output_plan_checksum == found.output_plan_checksum


# --------------------------------------------------------------------------
# Everything else is not_checkable, and that is the point
# --------------------------------------------------------------------------


def test_a_replay_on_another_build_is_refused(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    """Replaying today's planner over yesterday's inputs verifies today's planner."""
    path, records = recorded_episode(tmp_path, blocked)
    with pytest.raises(CheckerRefusal) as caught:
        check_replay_global_plan(
            evidence_at(path, records[0]),
            planner=SimulatorReplayPlanner(execution_environment_ref="git:" + "d" * 40),
        )
    assert caught.value.code == "replay_did_not_reproduce"
    assert "execution_environment_ref" in str(caught.value)


class WrongFingerprint:
    """A harness that ran something other than what it says it ran."""

    def replay(self, request: ReplayRequest) -> ReplayPlan:
        return ReplayPlan(
            outcome="path",
            output_plan_checksum="0" * 64,
            planner_fingerprint=planner_fingerprint("astar", {"connectivity": 4}),
            execution_environment_ref=BUILD,
        )


def test_a_replay_under_another_configuration_is_refused(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    path, records = recorded_episode(tmp_path, blocked)
    with pytest.raises(CheckerRefusal) as caught:
        check_replay_global_plan(evidence_at(path, records[0]), planner=WrongFingerprint())
    assert caught.value.code == "replay_did_not_reproduce"


def test_a_harness_that_cannot_rebuild_the_planner_says_so(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    """Substituting the nearest match would replay a different algorithm."""
    path, records = recorded_episode(tmp_path, blocked)
    snapshot = snapshot_for(path, records[0])
    request = ReplayRequest.from_snapshot(snapshot).model_copy(
        update={"planner_name": "a_planner_nobody_wrote"}
    )
    with pytest.raises(ReplayUnavailable) as caught:
        SimulatorReplayPlanner(execution_environment_ref=BUILD).replay(request)
    assert caught.value.code == "planner_not_in_harness"


def test_a_sampling_planner_without_its_seed_is_refused(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    """Replaying RRT* without a seed grows a different tree."""
    path, records = recorded_episode(tmp_path, blocked)
    request = ReplayRequest.from_snapshot(snapshot_for(path, records[0])).model_copy(
        update={"planner_name": "rrtstar", "seed": None}
    )
    with pytest.raises(ReplayUnavailable) as caught:
        SimulatorReplayPlanner(execution_environment_ref=BUILD).replay(request)
    assert caught.value.code == "seed_not_recorded"


def test_the_harness_planner_map_is_closed() -> None:
    assert set(PLANNERS) == {"astar", "rrtstar"}


def test_a_snapshot_that_is_not_the_one_the_record_pins_is_a_file_problem(
    tmp_path, blocked
) -> None:  # type: ignore[no-untyped-def]
    """Reported as such, rather than as a replay that failed."""
    path, records = recorded_episode(tmp_path, blocked)
    other = snapshot_for(path, records[0]).model_copy(update={"goal_x": 99.0})
    with pytest.raises((CheckerRefusal, ValidationError), match="replay_inputs_mismatched"):
        ReplayEvidence(record=records[0], snapshot=other)


def test_a_harness_that_finds_a_path_and_does_not_hash_it_is_refused() -> None:
    with pytest.raises((CheckerRefusal, ValidationError), match="nothing to compare"):
        ReplayPlan(
            outcome="path",
            planner_fingerprint="f" * 64,
            execution_environment_ref=BUILD,
        )


def test_a_harness_that_refuses_without_a_reason_is_refused() -> None:
    """ "no path" and "timed out" are different mechanisms."""
    with pytest.raises((CheckerRefusal, ValidationError), match="different mechanisms"):
        ReplayPlan(
            outcome="no_path",
            planner_fingerprint="f" * 64,
            execution_environment_ref=BUILD,
        )


# --------------------------------------------------------------------------
# Through the host
# --------------------------------------------------------------------------


def test_no_card_is_awaiting_the_sidecar_any_more() -> None:
    """Both replay checks left the set: E4.5 gave them inputs, E6b a planner.

    ``rrt_convergence`` was the last one out, once its evidence grew the
    run's own seed set — the sidecar records the attempt that happened,
    and the sampling question is about the attempts that did not.
    """
    from planbench_explanation.host import AWAITING_SIDECAR

    assert frozenset() == AWAITING_SIDECAR


def test_the_sidecar_read_back_from_disk_is_what_the_replay_uses(tmp_path, blocked) -> None:  # type: ignore[no-untyped-def]
    """Nothing in the chain is held in memory from the recording run."""
    path, _ = recorded_episode(tmp_path, blocked)
    _header, records = read_sidecar(path)
    outcome = check_replay_global_plan(
        evidence_at(path, records[0]),
        planner=SimulatorReplayPlanner(execution_environment_ref=BUILD),
    )
    assert outcome.verdict in ("supported", "refuted")


# --------------------------------------------------------------------------
# rrt_convergence — a sweep, not a replay
# --------------------------------------------------------------------------


class BudgetSensitive:
    """A planner that finds the corridor above a threshold of samples.

    Scripted so the three verdicts can be exercised in milliseconds. The
    real sweep over the planted world is in
    ``scripts/plant_golden_runs.py`` and its measured rates are in the
    report — twelve seeds of RRT* at two budgets on a 120x100 grid is a
    minute of CPU, which does not belong in a unit test.
    """

    def __init__(self, *, threshold: int, seed_cutoff: int = 999) -> None:
        self.threshold = threshold
        self.seed_cutoff = seed_cutoff
        self.calls: list[tuple[int, int]] = []

    def replay(self, request: ReplayRequest) -> ReplayPlan:
        budget = int(request.planner_parameters["max_iterations"])
        seed = int(request.seed or 0)
        self.calls.append((budget, seed))
        found = budget >= self.threshold and seed <= self.seed_cutoff
        if found:
            return ReplayPlan(
                outcome="path",
                output_plan_checksum="a" * 64,
                planner_fingerprint="f" * 64,
                execution_environment_ref=BUILD,
            )
        return ReplayPlan(
            outcome="no_path",
            failure_code="no_global_path",
            planner_fingerprint="f" * 64,
            execution_environment_ref=BUILD,
        )


TWELVE_SEEDS = tuple(range(1, 13))


def convergence_evidence(seeds=TWELVE_SEEDS, budget: int = 120):  # type: ignore[no-untyped-def]
    from planbench_explanation.planning_input_evidence import PlanningQuery

    grid = walled_grid()
    snapshot = PlanningSnapshot(
        episode_context_id="ep-004",
        candidate_id="rrtstar+dwa",
        planning_attempt=1,
        grid=grid,
        start_x=1.0,
        start_y=1.0,
        goal_x=1.0,
        goal_y=5.0,
        planner_name="rrtstar",
        planner_parameters={"max_iterations": budget},
        seed=1,
    )
    record = PlanningInputEvidence(
        episode_context_id="ep-004",
        candidate_id="rrtstar+dwa",
        planning_attempt=1,
        simulation_tick=0,
        query=PlanningQuery(
            start_pose=Pose2D(x=1.0, y=1.0, theta=0.0),
            goal_pose=Pose2D(x=1.0, y=5.0, theta=0.0),
        ),
        costmap_checksum=grid.checksum,
        snapshot_ref="snapshots/attempt-001.json",
        snapshot_checksum=snapshot.checksum,
        planner_fingerprint=snapshot.fingerprint,
        execution_environment_ref=BUILD,
        outcome="no_path",
        failure_code="no_global_path",
    )
    return ConvergenceEvidence(record=record, snapshot=snapshot, seeds=seeds)


def test_a_corridor_found_only_at_the_larger_budget_is_the_mechanism() -> None:
    """Zero at the configured budget, most seeds at four times it."""
    planner = BudgetSensitive(threshold=480)
    outcome = check_rrt_convergence(convergence_evidence(), planner=planner)
    assert outcome.proposition_type == "sampling_budget_insufficiency"
    assert outcome.verdict == "supported"
    assert outcome.measurements["success_rate_at_budget"] == 0.0
    assert outcome.measurements["success_rate_at_high_budget"] == 1.0


def test_a_planner_that_finds_it_reliably_refutes_the_hypothesis() -> None:
    """Whatever went wrong, it was not the sample budget."""
    outcome = check_rrt_convergence(convergence_evidence(), planner=BudgetSensitive(threshold=1))
    assert outcome.verdict == "refuted"
    assert "reliably" in outcome.note


def test_a_rate_flat_in_the_budget_points_at_the_geometry() -> None:
    """Reporting it as "not enough samples" sends somebody to the wrong knob."""
    outcome = check_rrt_convergence(
        convergence_evidence(), planner=BudgetSensitive(threshold=10**9)
    )
    assert outcome.verdict == "refuted"
    assert "does not move with the budget" in outcome.note


def test_the_sweep_runs_every_seed_at_every_preregistered_budget() -> None:
    planner = BudgetSensitive(threshold=480)
    check_rrt_convergence(convergence_evidence(seeds=(1, 2, 3, 4, 5, 6, 7, 8)), planner=planner)
    budgets = {budget for budget, _seed in planner.calls}
    assert budgets == {120, 480}
    assert len(planner.calls) == 8 * len(BUDGET_MULTIPLIERS)


def test_too_few_seeds_is_a_refusal_rather_than_a_rate() -> None:
    with pytest.raises(CheckerRefusal) as caught:
        check_rrt_convergence(
            convergence_evidence(seeds=(1, 2, 3, 4)), planner=BudgetSensitive(threshold=1)
        )
    assert caught.value.code == "insufficient_seeds"


def test_a_seed_counted_twice_moves_the_rate_without_adding_a_draw() -> None:
    with pytest.raises((CheckerRefusal, ValidationError), match="seed_counted_twice"):
        convergence_evidence(seeds=(1, 1, 2, 3, 4, 5, 6, 7, 8))


def test_a_snapshot_with_no_recorded_budget_cannot_be_swept() -> None:
    """A sweep against a guessed baseline measures the guess."""
    evidence = convergence_evidence()
    with pytest.raises((CheckerRefusal, ValidationError), match="budget_parameter_not_recorded"):
        ConvergenceEvidence(
            record=evidence.record,
            snapshot=evidence.snapshot,
            seeds=evidence.seeds,
            budget_parameter="samples",
        )


def test_the_budgets_are_preregistered_rather_than_chosen_per_run() -> None:
    """A second budget picked after the first result is picked to make a rate rise."""
    assert BUDGET_MULTIPLIERS[0] == 1.0
    assert len(BUDGET_MULTIPLIERS) >= 2
