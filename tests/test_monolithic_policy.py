"""HĐ-4's second candidate shape: a policy with no global planner.

Until now this platform could only run ``modular`` candidates, and
HĐ-4.1's clause named two things that had to be settled before a
``monolithic`` one was scored: the replan grid's information privilege
(gone in 6.6.0) and the adapter itself.

What these tests defend is not that a policy drives well — the reference
policy here is nine lines of trigonometry and is meant to be
uninteresting. It is that a policy runs through **the same loop** as
every other candidate and is neither given nor charged anything a
modular stack is not.
"""

from __future__ import annotations

import inspect
import math

import pytest
from blocked_route import blocked_robot, two_doorway_map

from planbench_planning import DWAPlanner
from planbench_planning.common.local_base import LocalPlanResult
from planbench_planning.common.policy_base import MonolithicPolicy
from planbench_planning.common.reference_policy import GreedyReferencePolicy
from planbench_schemas.episode import EpisodeStatus, Observation
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig, RobotState, SimAction
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import NO_GLOBAL_PLANNING, run_policy, run_stack


@pytest.fixture
def robot() -> RobotConfig:
    return blocked_robot()


@pytest.fixture
def open_run(robot: RobotConfig) -> Scenario:
    """A short straight run with nothing in the way.

    Deliberately easy: this file tests the harness, and a scenario the
    reference policy could fail would be testing the policy.
    """
    return Scenario(
        name="policy-open-run",
        robot=robot,
        start_pose=Pose2D(x=2.0, y=3.5, theta=0.0),
        goal_pose=Pose2D(x=7.0, y=3.5, theta=0.0),
        goal_tolerance=0.5,
        timeout_seconds=60.0,
        simulation_dt=0.05,
    )


class TestAPolicyRunsThroughTheSameLoop:
    def test_it_reaches_a_goal_with_no_global_plan(self, open_run: Scenario) -> None:
        run = run_policy(two_doorway_map(), open_run, GreedyReferencePolicy())
        assert run.result.status is EpisodeStatus.SUCCESS, run.result.reason
        assert run.plan.path == (), "a monolithic candidate must be handed no path"

    def test_no_route_search_is_charged_to_it(self, open_run: Scenario) -> None:
        """A candidate that runs no global search spends nothing on one.
        Charging it a number would price work it did not do."""
        run = run_policy(two_doorway_map(), open_run, GreedyReferencePolicy())
        assert run.plan.planning_time_seconds == 0.0
        assert run.plan.expanded_nodes == 0
        assert run.plan.path_length == 0.0

    def test_planning_nothing_is_not_the_same_as_finding_no_route(self, open_run: Scenario) -> None:
        """``success=False`` is how the loop records *no route exists*,
        and G1 counts exactly that. A policy that was never asked to find
        a route must not land in that count."""
        run = run_policy(two_doorway_map(), open_run, GreedyReferencePolicy())
        assert run.plan.success is True
        assert run.result.status is not EpisodeStatus.NO_GLOBAL_PATH

    def test_it_is_named_by_one_name(self, open_run: Scenario) -> None:
        """One layer, one name. ``none+policy`` would read as a stack
        whose global planner happened to be missing, which is a different
        candidate from one that has none by construction (HĐ-1.2)."""
        run = run_policy(two_doorway_map(), open_run, GreedyReferencePolicy())
        assert run.algorithm == "greedy_reference_policy"
        assert "+" not in run.algorithm

    def test_a_modular_stack_on_the_same_scenario_is_still_named_by_two(
        self, open_run: Scenario
    ) -> None:
        run = run_stack(two_doorway_map(), open_run, DWAPlanner())
        assert "+" in run.algorithm


class TestThePolicyNeverSeesAGlobalPath:
    """The one difference from a modular stack, asserted rather than
    assumed. A policy that peeked at a path would be a modular stack
    wearing a policy's label, and nothing else would notice."""

    def test_reset_drops_the_path_it_is_handed(self, robot: RobotConfig) -> None:
        seen: list[object] = []

        class Nosy(MonolithicPolicy):
            @property
            def name(self) -> str:
                return "nosy"

            def prepare(self, robot: RobotConfig) -> None:
                seen.append(robot)

            def decide(self, state: RobotState, observation: Observation) -> LocalPlanResult:
                return LocalPlanResult(action=SimAction(linear_velocity=0.0, angular_velocity=0.0))

        policy = Nosy()
        policy.reset((Point2D(x=1.0, y=1.0), Point2D(x=2.0, y=2.0)), robot)
        assert seen == [robot], "prepare() gets the robot and nothing else"
        assert not hasattr(policy, "_global_path")

    def test_the_base_class_forwards_no_path_to_subclasses(self) -> None:
        """``reset`` takes the path only because the driving loop is
        shared — and sharing that loop is what makes the comparison a
        comparison. It must not reach ``decide``."""
        import inspect

        source = inspect.getsource(MonolithicPolicy.reset)
        assert "del global_path" in source


class TestTheNullPlannerReportsTheTruth:
    def test_it_plans_nothing_in_no_time(self) -> None:
        from planbench_simulator.grid import OccupancyGrid

        grid = OccupancyGrid(two_doorway_map())
        result = NO_GLOBAL_PLANNING.plan(grid, Point2D(x=1.0, y=1.0), Point2D(x=2.0, y=2.0))
        assert result.success is True
        assert result.path == ()
        assert result.expanded_nodes == 0

    def test_it_is_not_offered_as_a_default(self) -> None:
        """``run_stack`` with no global planner still means A*. A default
        that silently planned nothing would turn every modular stack into
        a policy on the day somebody forgot an argument."""
        from planbench_simulator import nav_stack

        source = inspect.getsource(nav_stack.run_stack)
        assert "global_planner or AStarPlanner()" in source


class TestReplanningIsNotOfferedToAPolicy:
    def test_a_policy_run_asks_for_none(self) -> None:
        """Replanning replaces a global path; a policy has none, so a
        budget here would be a control with nothing behind it."""
        import inspect

        from planbench_simulator import nav_stack

        source = inspect.getsource(nav_stack.run_policy)
        assert "NO_REPLANNING" in source

    def test_the_reference_policy_is_marked_as_never_a_candidate(self) -> None:
        """Same rule ``PurePursuitLocalPlanner`` carries (decision D12):
        a reference implementation that drifted into a comparison would
        put nine lines of trigonometry beside a trained stack."""
        import inspect

        from planbench_planning.common import reference_policy

        doc = inspect.getdoc(reference_policy) or ""
        assert "Never a candidate" in doc
        assert "not benchmarkable" in doc


class TestTheReferencePolicyIsDeterministic:
    """The precondition every candidate must meet (HĐ-4): identical
    inputs give identical commands, or a re-run is not a re-run."""

    def test_the_same_observation_gives_the_same_command(self, robot: RobotConfig) -> None:
        policy = GreedyReferencePolicy()
        policy.reset((), robot)
        state = RobotState(pose=Pose2D(x=1.0, y=1.0, theta=0.0))
        observation = Observation(
            time=0.0,
            pose=state.pose,
            linear_velocity=0.0,
            angular_velocity=0.0,
            goal_distance=4.0,
            goal_bearing=math.pi / 8,
            lidar_ranges=tuple([5.0] * 72),
        )
        first = policy.decide(state, observation).action
        again = policy.decide(state, observation).action
        assert first == again
