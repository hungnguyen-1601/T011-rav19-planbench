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

import pytest
from blocked_route import blocked_robot, two_doorway_map
from blocked_route import blocked_scenario as build_blocked_scenario
from pydantic import ValidationError

from planbench_benchmark.spec import AlgorithmSpec, BenchmarkSpec, FairnessRecord
from planbench_metrics.definitions import EpisodeMetricSet
from planbench_planning import DWAPlanner, RRTStarConfig, RRTStarPlanner
from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.nav_stack import run_stack

# The map and the blocked scenario live in ``tests/blocked_route.py``:
# the API suite runs the same premise through ``/simulate``, and the two
# must not drift apart.


@pytest.fixture
def robot() -> RobotConfig:
    return blocked_robot()


@pytest.fixture
def blocked_scenario(robot: RobotConfig) -> Scenario:
    return build_blocked_scenario(robot)


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


class TestReplanningIsPricedRatherThanCapped:
    """No budget, and a bill instead.

    ``max_replans`` used to be a required cap. The reasoning behind it was
    sound — an unbounded budget turns *"did the planner recover?"* into
    *"did the timeout arrive first?"* — and the cure was worse: a shared
    cap is a number **somebody chose**, it binds differently for
    different stacks, and under a budget of three a stack that would have
    escaped on its fourth try is scored as a failure of the budget rather
    than of the planner. Same class of artifact as the replan information
    privilege (HĐ-4.1): an evaluation condition quietly deciding a result.

    What replaces it is the price. Every replan records its own
    control-step row carrying the global planner's latency, so G4 pools
    it with the rest. p99 cuts at the 99th percentile, so a couple of
    replans in four hundred steps sit above the cut and cost nothing,
    while habitual replanning walks into the latency gate on its own —
    **the ceiling grows out of the physics instead of being declared**.
    """

    def test_the_budget_defaults_to_unlimited_when_enabled(self) -> None:
        config = ReplanningConfig(enabled=True)
        assert config.max_replans is None
        assert config.allows(1_000_000)

    def test_an_explicit_cap_still_caps(self) -> None:
        """The retiring benchmark flow stores specs naming one, and a
        stored run must keep describing the conditions it ran under."""
        config = ReplanningConfig(enabled=True, max_replans=2)
        assert config.allows(2)
        assert not config.allows(3)

    def test_disabled_allows_nothing_however_the_budget_reads(self) -> None:
        assert not ReplanningConfig(enabled=False).allows(0)
        assert not ReplanningConfig(enabled=False, max_replans=0).allows(0)

    def test_enabling_with_a_budget_of_zero_is_still_refused(self) -> None:
        """It would do nothing while reading as if it did something."""
        with pytest.raises(ValidationError, match="does nothing"):
            ReplanningConfig(enabled=True, max_replans=0)

    def test_the_historical_default_is_unchanged(self) -> None:
        """`is_default` keeps pre-replanning checksums byte-identical."""
        assert NO_REPLANNING.is_default
        assert not ReplanningConfig(enabled=True).is_default


class TestAReplanIsChargedForAsAControlStep:
    """The bill, measured rather than asserted.

    Before this, `_replan` ran outside the recording branch: G4 pooled
    its p99 over a set of local-controller steps that contained no replan
    at all, so replanning was free by construction. This drives a real
    episode on the scenario that needs one and reads the trace back.
    """

    def _run(self, tmp_path, config):
        from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
        from planbench_benchmark.registry import build_global_planner, build_local_planner
        from planbench_benchmark.scenarios import build_scenario
        from planbench_schemas.episode_context import EpisodeContext
        from planbench_simulator.trace import EpisodeTraceRecorder

        map_data, scenario = build_scenario("sudden_stop")
        context = EpisodeContext(task_profile_id="p", mission_id="m", seed=0)
        with EpisodeTraceRecorder(
            context, "cand", root=tmp_path, costmap_cells=map_data.width * map_data.height
        ) as recorder:
            run = run_stack(
                map_data,
                scenario,
                build_local_planner("astar+dwa", dict(LOCAL_CONTROLLER_CONFIGS["dwa_coarse"])),
                build_global_planner("astar+dwa", episode_seed=0),
                config,
                recorder=recorder,
                legacy_metrics=False,
            )
            recorder.close(
                peak_search_nodes=run.plan.expanded_nodes,
                peak_tree_nodes=0,
                global_plan_length_m=run.plan.path_length if run.plan.success else None,
                global_plan_time_ms=run.plan.planning_time_seconds * 1000.0,
            )
        return recorder.path, run

    def test_the_trace_carries_a_replan_row_with_the_planner_time_on_it(self, tmp_path) -> None:
        """Without this row the cost model does not exist."""
        import pandas as pd

        path, _ = self._run(tmp_path, ReplanningConfig(enabled=True))
        frame = pd.read_parquet(path)
        replans = frame[frame["event"] == "replan"]
        assert len(replans) >= 1, "the episode that needs a replan recorded none"

        # The claim is that the replan was *charged for*: every replan row
        # carries the time it actually cost, so a stack that replans often
        # cannot look as cheap as one that does not. A row present with a
        # zero on it would be the cost model quietly not existing.
        assert (replans["planner_latency_ms"] > 0).all()

        # Not against a fixed millisecond figure. The first version
        # asserted `> 50 ms`, calibrated on the 480x320 hall where A*
        # takes ~740 ms, and failed here: `sudden_stop` is 14x9 m and the
        # same planner takes ~5 ms, about twice a control step rather than
        # sixty times. **The price of a replan scales with the map**, so
        # on a small scenario replanning is nearly free and on a real
        # deployment map it is not.
        #
        # Nor against the 99th percentile of ordinary steps, which is what
        # replaced the fixed figure and was flaky about one run in three.
        # On this map the two distributions overlap: a replan lands around
        # 6.5 ms and the p99 of ordinary steps around 5.7 ms — a margin of
        # 1.12x, inside the noise, and the slowest ordinary step routinely
        # beats the fastest replan. The p99 of ordinary steps is the worst
        # scheduling hiccup the OS handed out during the episode; it
        # measures the machine, not the planner, and on a two-core hosted
        # runner it measures a busier one.
        #
        # The median does measure the planner, and a replan running a full
        # global search costs about twice an ordinary control step here.
        # That is the weaker claim, and it is the one this map can carry
        # honestly. A scenario large enough for the p99 claim would be a
        # different test on a different map, not a tighter assertion here.
        ordinary = frame[frame["event"].isna() | (frame["event"] == "")]
        assert replans["planner_latency_ms"].max() > ordinary["planner_latency_ms"].median()

    def test_without_replanning_the_trace_has_no_such_row(self, tmp_path) -> None:
        import pandas as pd

        path, _ = self._run(tmp_path, NO_REPLANNING)
        frame = pd.read_parquet(path)
        assert (frame["event"] == "replan").sum() == 0

    def test_unlimited_replanning_gets_the_robot_there(self, tmp_path) -> None:
        """The point of the change, end to end.

        `sudden_stop` puts a cart in the lane and stops it dead. With no
        replanning the robot gives up; with replanning it goes around.
        """
        _, without = self._run(tmp_path / "off", NO_REPLANNING)
        _, with_replans = self._run(tmp_path / "on", ReplanningConfig(enabled=True))
        assert without.result.status is EpisodeStatus.STUCK
        assert with_replans.result.status is EpisodeStatus.SUCCESS


class TestTheReplanCountIsEvidenceAndNotAScore:
    """Deliberately outside the objective function.

    Replanning costs time and latency; ``travel_time_s`` and
    ``p99_latency_ms`` already charge for both. A penalty term would
    price the same thing twice, and its weight would be one more number
    somebody chose — the exact knob that removing ``max_replans`` was
    meant to be rid of.
    """

    def test_it_is_a_metric(self) -> None:
        assert "replan_count" in EpisodeMetricSet.model_fields

    def test_the_objective_layer_never_reads_it(self) -> None:
        """The promise, as a fact about the source rather than a comment.

        If somebody later scores it, this fails and they get to argue for
        it on purpose instead of by accident.
        """
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "packages" / "decision"
        for module in ("objectives.py", "stats.py", "pareto.py"):
            text = (root / "planbench_decision" / module).read_text(encoding="utf-8")
            assert "replan" not in text, f"{module} now reads replan_count; that is a score"

    def test_no_gate_reads_it_either(self) -> None:
        from pathlib import Path

        gates = (
            Path(__file__).resolve().parents[1]
            / "packages"
            / "decision"
            / "planbench_decision"
            / "gates.py"
        )
        assert "replan" not in gates.read_text(encoding="utf-8")
