"""Replanning when a dynamic obstacle blocks the path (plan 4.1).

The centre of gravity here is the premise test: replanning off leaves the
robot stuck, replanning on gets it to the goal on the *same* scenario and
the same seed. Everything else in this file guards a way the feature
could look like it works while quietly being unfair — a replan budget
granted to one stack and not another, a conditions checksum that does not
notice the rule changed, or a stuck window that was never reseeded so the
"recovery" is one step long.
"""

from __future__ import annotations

import math

import pytest

from planbench_benchmark.spec import AlgorithmSpec, BenchmarkSpec, FairnessRecord
from planbench_planning import DWAPlanner, RRTStarConfig, RRTStarPlanner
from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_schemas.dynamic import DynamicObstacle, SuddenStopMotion
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.nav_stack import run_stack

# A room split by a wall with two doorways. The short way through is the
# lower one; a cart parks in it before the robot arrives. Nothing about
# the map changes — the only route to the goal that remains is the upper
# doorway, and only a planner that is told where the cart is can find it.
RESOLUTION = 0.5
WIDTH, HEIGHT = 40, 28
WALL_COL = 20
LOWER_DOORWAY = range(4, 11)
UPPER_DOORWAY = range(17, 24)


def two_doorway_map() -> MapData:
    cells = [CellState.FREE.value] * (WIDTH * HEIGHT)

    def occupy(row: int, col: int) -> None:
        cells[row * WIDTH + col] = CellState.OCCUPIED.value

    for col in range(WIDTH):
        occupy(0, col)
        occupy(HEIGHT - 1, col)
    for row in range(HEIGHT):
        occupy(row, 0)
        occupy(row, WIDTH - 1)
    for row in range(1, HEIGHT - 1):
        if row not in LOWER_DOORWAY and row not in UPPER_DOORWAY:
            occupy(row, WALL_COL)
    return MapData(
        name="two-doorway-room",
        width=WIDTH,
        height=HEIGHT,
        resolution=RESOLUTION,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(cells),
    )


@pytest.fixture
def robot() -> RobotConfig:
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=3.0,
    )


@pytest.fixture
def blocked_scenario(robot: RobotConfig) -> Scenario:
    """Lower doorway blocked by a cart that parks before the robot arrives.

    The cart starts clear of both the start and the goal (the engine
    rejects a scenario whose robot begins inside an obstacle) and rolls
    into the doorway, stopping there for good at t = 5 s. The robot needs
    about eight seconds to cross the room, so it always meets a parked
    cart rather than a moving one: the episode tests recovery from a
    blocked route, not luck with timing.
    """
    return Scenario(
        name="doorway-blocked",
        robot=robot,
        start_pose=Pose2D(x=2.0, y=3.5, theta=0.0),
        goal_pose=Pose2D(x=18.0, y=3.5, theta=0.0),
        goal_tolerance=0.4,
        timeout_seconds=240.0,
        simulation_dt=0.05,
        dynamic_obstacles=(
            DynamicObstacle(
                name="parked-cart",
                radius=1.8,
                motion=SuddenStopMotion(
                    start=Point2D(x=10.25, y=6.0),
                    heading=-math.pi / 2,
                    speed=0.5,
                    stop_time=5.0,
                ),
            ),
        ),
    )


class CountingPlanner(GlobalPlanner):
    """Always succeeds, always returns the same useless path, counts calls.

    Stands in for the case the budget exists for: a planner that has no
    better idea. Without a cap the stack would replan on every step for
    the rest of the episode.
    """

    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "counting"

    def plan(self, grid, start: Point2D, goal: Point2D) -> PlanResult:  # noqa: ANN001, ARG002
        self.calls += 1
        return PlanResult(success=True, path=(start, start), path_length=0.0, expanded_nodes=1)


def simple_scenario(robot: RobotConfig, **overrides) -> Scenario:
    defaults: dict = {
        "name": "replanning-fairness",
        "robot": robot,
        "start_pose": Pose2D(x=2.5, y=2.5, theta=0.0),
        "goal_pose": Pose2D(x=9.5, y=9.5, theta=0.0),
        "goal_tolerance": 0.4,
        "timeout_seconds": 120.0,
        "simulation_dt": 0.05,
    }
    defaults.update(overrides)
    return Scenario(**defaults)


class TestReplanningConfig:
    def test_defaults_to_the_behaviour_that_existed_before_it(self) -> None:
        assert NO_REPLANNING.enabled is False
        assert NO_REPLANNING.max_replans == 0
        assert NO_REPLANNING.is_default

    def test_enabling_with_a_zero_budget_is_rejected(self) -> None:
        # Silently doing nothing would be the worst outcome: the report
        # would claim replanning was on while no robot ever replanned.
        with pytest.raises(ValueError, match="does nothing"):
            ReplanningConfig(enabled=True, max_replans=0)

    def test_negative_budget_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            ReplanningConfig(enabled=True, max_replans=-1)


class TestPremise:
    """Does the feature change the outcome, or only run without error?"""

    def test_blocked_route_ends_stuck_without_replanning(self, blocked_scenario: Scenario) -> None:
        run = run_stack(two_doorway_map(), blocked_scenario, DWAPlanner())
        assert run.result.status is EpisodeStatus.STUCK
        assert run.metrics.replan_count == 0

    def test_same_scenario_reaches_the_goal_with_replanning(
        self, blocked_scenario: Scenario
    ) -> None:
        run = run_stack(
            two_doorway_map(),
            blocked_scenario,
            DWAPlanner(),
            None,
            ReplanningConfig(enabled=True, max_replans=3),
        )
        assert run.result.status is EpisodeStatus.SUCCESS
        assert run.metrics.replan_count is not None and run.metrics.replan_count >= 1
        # The new route went through the other doorway, which is up and
        # around: recovery costs time, and the report should show it.
        assert run.result.elapsed_time > 20.0

    def test_the_replan_is_recorded_as_an_event_and_the_stuck_verdict_is_not(
        self, blocked_scenario: Scenario
    ) -> None:
        run = run_stack(
            two_doorway_map(),
            blocked_scenario,
            DWAPlanner(),
            None,
            ReplanningConfig(enabled=True, max_replans=3),
        )
        types = [event.type for event in run.result.events]
        assert "replan" in types
        # The episode did not end stuck, so no stuck termination may sit
        # in its record claiming otherwise.
        assert EpisodeStatus.STUCK.value not in types

    def test_planning_cost_is_the_total_across_every_plan(self, blocked_scenario: Scenario) -> None:
        once = run_stack(two_doorway_map(), blocked_scenario, DWAPlanner())
        twice = run_stack(
            two_doorway_map(),
            blocked_scenario,
            DWAPlanner(),
            None,
            ReplanningConfig(enabled=True, max_replans=3),
        )
        assert once.metrics.expanded_nodes is not None
        assert twice.metrics.expanded_nodes is not None
        assert twice.metrics.expanded_nodes > once.metrics.expanded_nodes

    @pytest.mark.parametrize("budget", [1, 2, 3])
    def test_the_budget_is_a_hard_cap_even_when_replanning_never_helps(
        self, robot: RobotConfig, bordered_map_factory, budget: int
    ) -> None:
        """A planner that keeps handing back a useless path must not loop.

        The premise tests show recovery working; this one shows the
        opposite case terminating. ``CountingPlanner`` always succeeds
        and always returns the same one-step path, so the robot is stuck
        again immediately and the only thing that ends the episode is the
        budget running out.
        """
        planner = CountingPlanner()
        run = run_stack(
            bordered_map_factory(14, 14),
            simple_scenario(robot, stuck_time_window=1.0, stuck_min_displacement=0.2),
            DWAPlanner(),
            planner,
            ReplanningConfig(enabled=True, max_replans=budget),
        )
        assert run.metrics.replan_count == budget
        # One initial plan plus exactly ``budget`` replans, no more.
        assert planner.calls == budget + 1
        assert run.result.status is not EpisodeStatus.SUCCESS

    def test_rrtstar_replans_onto_a_valid_path(self, blocked_scenario: Scenario) -> None:
        # A sampling planner has to survive being asked for a second tree
        # mid-episode; the seed plumbing is per-episode, not per-plan.
        run = run_stack(
            two_doorway_map(),
            blocked_scenario,
            DWAPlanner(),
            RRTStarPlanner(RRTStarConfig(max_iterations=6000), episode_seed=3),
            ReplanningConfig(enabled=True, max_replans=3),
        )
        assert run.metrics.replan_count is not None and run.metrics.replan_count >= 1
        assert run.result.status is not EpisodeStatus.COLLISION


class TestDisabledIsUnchanged:
    def test_disabled_run_matches_a_run_that_never_heard_of_replanning(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(14, 14)
        scenario = simple_scenario(robot)
        without = run_stack(map_data, scenario, DWAPlanner())
        disabled = run_stack(map_data, scenario, DWAPlanner(), None, NO_REPLANNING)
        assert without.result.status is disabled.result.status
        assert without.result.trajectory == disabled.result.trajectory
        assert without.metrics.replan_count == 0


class TestFairness:
    """The rule is a condition of the benchmark, not a gift to one stack."""

    def test_two_algorithms_under_one_rule_share_a_checksum(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(14, 14)
        scenario = simple_scenario(robot)
        rule = ReplanningConfig(enabled=True, max_replans=2)
        assert (
            FairnessRecord.build(map_data, scenario, (1, 2), rule).conditions_checksum
            == FairnessRecord.build(map_data, scenario, (1, 2), rule).conditions_checksum
        )

    def test_changing_the_rule_changes_the_checksum(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(14, 14)
        scenario = simple_scenario(robot)
        two = FairnessRecord.build(
            map_data, scenario, (1,), ReplanningConfig(enabled=True, max_replans=2)
        )
        three = FairnessRecord.build(
            map_data, scenario, (1,), ReplanningConfig(enabled=True, max_replans=3)
        )
        assert two.conditions_checksum != three.conditions_checksum
        assert (
            two.conditions_checksum
            != FairnessRecord.build(map_data, scenario, (1,)).conditions_checksum
        )

    def test_disabled_leaves_stored_checksums_untouched(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        # The field shipping must not tell everyone their old benchmarks
        # became incomparable overnight. This is the assertion that says
        # the checksum of a no-replanning run is the historical one.
        map_data = bordered_map_factory(14, 14)
        scenario = simple_scenario(robot)
        legacy = FairnessRecord.build(map_data, scenario, (1, 2, 3))
        explicit = FairnessRecord.build(map_data, scenario, (1, 2, 3), NO_REPLANNING)
        assert legacy.conditions_checksum == explicit.conditions_checksum

    def test_the_record_states_the_rule(self, bordered_map_factory, robot: RobotConfig) -> None:
        record = FairnessRecord.build(
            bordered_map_factory(14, 14),
            simple_scenario(robot),
            (1,),
            ReplanningConfig(enabled=True, max_replans=4),
        )
        assert record.replanning_enabled is True
        assert record.max_replans == 4

    def test_the_rule_lives_on_the_spec_not_on_an_algorithm(self) -> None:
        spec = BenchmarkSpec(
            name="one-rule",
            algorithms=(AlgorithmSpec(id="astar+dwa"), AlgorithmSpec(id="rrtstar+dwa")),
            seeds=(1, 2),
            replanning=ReplanningConfig(enabled=True, max_replans=2),
        )
        assert spec.replanning.max_replans == 2
        # Nothing per-algorithm can override it: the config dicts are the
        # local planner's, and the runner reads the rule from the spec.
        assert all(not algorithm.config for algorithm in spec.algorithms)

    def test_a_spec_written_before_the_field_existed_still_loads(self) -> None:
        spec = BenchmarkSpec.model_validate(
            {"name": "old", "algorithms": [{"id": "astar+dwa"}], "seeds": [1]}
        )
        assert spec.replanning == NO_REPLANNING


class TestEngineResume:
    """The half of the fix that is easy to forget: the stuck window."""

    def _stuck_engine(self, robot: RobotConfig, bordered_map_factory) -> SimulationEngine:
        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(14, 14))
        engine.load_scenario(
            simple_scenario(robot, stuck_time_window=1.0, stuck_min_displacement=0.2)
        )
        engine.reset()
        from planbench_schemas.robot import SimAction

        idle = SimAction(linear_velocity=0.0, angular_velocity=0.0)
        while not engine.is_done():
            engine.step(idle)
        assert engine.episode_status is EpisodeStatus.STUCK
        return engine

    def test_resume_does_not_immediately_re_derive_stuck(
        self, robot: RobotConfig, bordered_map_factory
    ) -> None:
        from planbench_schemas.robot import SimAction

        engine = self._stuck_engine(robot, bordered_map_factory)
        engine.resume_after_replan("new path")
        # Standing still again. Had the window kept its old samples, the
        # very next step would repeat the verdict and the replan would
        # have bought exactly one simulation step.
        engine.step(SimAction(linear_velocity=0.0, angular_velocity=0.0))
        assert engine.episode_status is EpisodeStatus.RUNNING
        assert not engine.is_done()

    def test_resume_replaces_the_termination_with_a_replan_event(
        self, robot: RobotConfig, bordered_map_factory
    ) -> None:
        engine = self._stuck_engine(robot, bordered_map_factory)
        engine.resume_after_replan("around the cart")
        engine.stop()
        types = [event.type for event in engine.get_result().events]
        assert "replan" in types
        assert EpisodeStatus.STUCK.value not in types

    def test_resume_is_refused_when_nothing_ended(
        self, robot: RobotConfig, bordered_map_factory
    ) -> None:
        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(14, 14))
        engine.load_scenario(simple_scenario(robot))
        engine.reset()
        with pytest.raises(RuntimeError, match="cannot resume after replan"):
            engine.resume_after_replan("nothing to recover from")

    def test_resume_is_refused_after_a_collision(
        self, robot: RobotConfig, bordered_map_factory
    ) -> None:
        from planbench_schemas.robot import SimAction

        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(14, 14))
        engine.load_scenario(simple_scenario(robot, start_pose=Pose2D(x=2.5, y=2.5, theta=0.0)))
        engine.reset()
        # Drive straight into the border wall.
        drive = SimAction(linear_velocity=1.0, angular_velocity=0.0)
        while not engine.is_done():
            engine.step(drive)
        assert engine.episode_status is EpisodeStatus.COLLISION
        with pytest.raises(RuntimeError, match="cannot resume after replan"):
            engine.resume_after_replan("a new path does not undo a crash")

    def test_dynamic_obstacle_positions_are_readable_at_the_current_time(
        self, blocked_scenario: Scenario
    ) -> None:
        engine = SimulationEngine()
        engine.load_map(two_doorway_map())
        engine.load_scenario(blocked_scenario)
        engine.reset()
        at_start = engine.dynamic_obstacles_now()
        assert len(at_start) == 1
        assert at_start[0].center.y == pytest.approx(6.0)


class TestControllerResetMidEpisode:
    """``LocalPlanner.reset()`` was written for episode start; replanning
    calls it again halfway through. These check nothing survives it."""

    def test_dwa_forgets_the_old_path_and_the_old_command(self, robot: RobotConfig) -> None:
        from planbench_schemas.episode import Observation
        from planbench_schemas.robot import RobotState

        planner = DWAPlanner()
        first = (Point2D(x=0.0, y=0.0), Point2D(x=5.0, y=0.0))
        planner.reset(first, robot)
        state = RobotState(pose=Pose2D(x=0.0, y=0.0, theta=0.0))
        observation = Observation(
            time=0.0,
            pose=state.pose,
            linear_velocity=0.0,
            angular_velocity=0.0,
            goal_distance=5.0,
            goal_bearing=0.0,
            lidar_ranges=(10.0,) * 8,
        )
        planner.compute(state, observation)
        second = (Point2D(x=0.0, y=0.0), Point2D(x=0.0, y=5.0))
        planner.reset(second, robot)
        assert planner._path == second  # noqa: SLF001 - the point of the test
        assert planner._path_index == 0  # noqa: SLF001
        assert planner._previous is None  # noqa: SLF001

    def test_ppo_forgets_the_old_path(self, robot: RobotConfig) -> None:
        pytest.importorskip(
            "stable_baselines3",
            reason="optional: PPO needs the RL extras from requirements-optional.txt",
        )
        from planbench_rl.policy import PPOLocalPlanner

        planner = PPOLocalPlanner.__new__(PPOLocalPlanner)
        planner._path = ()  # noqa: SLF001
        planner._robot = None  # noqa: SLF001
        second = (Point2D(x=0.0, y=0.0), Point2D(x=0.0, y=5.0))
        PPOLocalPlanner.reset(planner, second, robot)
        assert planner._path == second  # noqa: SLF001
        assert planner._robot is robot  # noqa: SLF001
