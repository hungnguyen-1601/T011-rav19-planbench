"""End-to-end tests for navigation stacks (A* + local planner)."""

from __future__ import annotations

import pytest

from planbench_planning import DWAConfig, DWAPlanner, RRTStarConfig, RRTStarPlanner
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import PurePursuitLocalPlanner, run_stack


@pytest.fixture
def robot() -> RobotConfig:
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=3.0,
    )


def make_scenario(robot: RobotConfig, **overrides) -> Scenario:
    defaults: dict = {
        "name": "stack-test",
        "robot": robot,
        "start_pose": Pose2D(x=2.5, y=2.5, theta=0.0),
        "goal_pose": Pose2D(x=9.5, y=9.5, theta=0.0),
        "goal_tolerance": 0.4,
        "timeout_seconds": 120.0,
        "simulation_dt": 0.05,
    }
    defaults.update(overrides)
    return Scenario(**defaults)


class TestAStarDWAStack:
    def test_reaches_the_goal_in_an_open_map(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        run = run_stack(bordered_map_factory(14, 14), make_scenario(robot), DWAPlanner())
        assert run.algorithm == "astar+dwa"
        assert run.plan.success
        assert run.result.status is EpisodeStatus.SUCCESS
        assert run.metrics.success
        assert run.metrics.mean_local_planning_latency is not None
        assert run.metrics.max_local_planning_latency is not None

    def test_never_collides_while_detouring_around_a_wall(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(16, 16, occupied=tuple((row, 8) for row in range(1, 12)))
        scenario = make_scenario(
            robot,
            start_pose=Pose2D(x=3.5, y=3.5, theta=0.0),
            goal_pose=Pose2D(x=12.5, y=3.5, theta=0.0),
            timeout_seconds=180.0,
            # The detour rounds the wall from above, so straight-line goal
            # distance grows for a long stretch: widen the FTP window.
            progress_time_window=90.0,
        )
        run = run_stack(map_data, scenario, DWAPlanner())
        assert run.result.status is EpisodeStatus.SUCCESS, run.result.reason
        assert not run.metrics.collision
        assert run.metrics.min_clearance is not None and run.metrics.min_clearance > 0.0

    def test_respects_robot_limits_along_the_whole_episode(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        run = run_stack(bordered_map_factory(14, 14), make_scenario(robot), DWAPlanner())
        for point in run.result.trajectory:
            assert abs(point.linear_velocity) <= robot.max_linear_velocity + 1e-12
            assert abs(point.angular_velocity) <= robot.max_angular_velocity + 1e-12
        dt = 0.05
        for previous, current in zip(
            run.result.trajectory, run.result.trajectory[1:], strict=False
        ):
            assert abs(current.linear_velocity - previous.linear_velocity) <= (
                robot.max_linear_acceleration * dt + 1e-9
            )
            assert abs(current.angular_velocity - previous.angular_velocity) <= (
                robot.max_angular_acceleration * dt + 1e-9
            )

    def test_deterministic_across_runs(self, bordered_map_factory, robot: RobotConfig) -> None:
        map_data = bordered_map_factory(14, 14, occupied=((6, 6), (6, 7), (7, 6)))
        scenario = make_scenario(robot)
        first = run_stack(map_data, scenario, DWAPlanner())
        second = run_stack(map_data, scenario, DWAPlanner())
        assert first.result.trajectory == second.result.trajectory
        assert first.metrics.trajectory_length == second.metrics.trajectory_length

    def test_config_changes_behaviour(self, bordered_map_factory, robot: RobotConfig) -> None:
        map_data = bordered_map_factory(14, 14)
        scenario = make_scenario(robot)
        cautious = run_stack(
            map_data, scenario, DWAPlanner(DWAConfig(weight_velocity=0.0, weight_clearance=4.0))
        )
        eager = run_stack(map_data, scenario, DWAPlanner(DWAConfig(weight_velocity=2.0)))
        assert cautious.result.trajectory != eager.result.trajectory

    def test_no_global_path_short_circuits(self, bordered_map_factory, robot: RobotConfig) -> None:
        map_data = bordered_map_factory(12, 12, occupied=tuple((row, 6) for row in range(12)))
        run = run_stack(
            map_data,
            make_scenario(robot, goal_pose=Pose2D(x=9.5, y=2.5, theta=0.0)),
            DWAPlanner(),
        )
        assert not run.plan.success
        assert run.result.status is EpisodeStatus.NO_GLOBAL_PATH
        assert run.result.events[0].type == "no_global_path"


class TestRRTStarDWAStack:
    def test_reaches_the_goal_with_rrtstar_as_the_global_planner(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        run = run_stack(
            bordered_map_factory(14, 14),
            make_scenario(robot),
            DWAPlanner(),
            RRTStarPlanner(RRTStarConfig(max_iterations=1000, seed=1)),
        )
        assert run.algorithm == "rrtstar+dwa"
        assert run.plan.success
        assert run.result.status is EpisodeStatus.SUCCESS
        assert run.metrics.success
        assert not run.metrics.collision


class TestPurePursuitStackAdapter:
    def test_reference_stack_still_runs(self, bordered_map_factory, robot: RobotConfig) -> None:
        run = run_stack(
            bordered_map_factory(12, 12), make_scenario(robot), PurePursuitLocalPlanner()
        )
        assert run.algorithm == "astar+pure_pursuit"
        assert run.result.status is EpisodeStatus.SUCCESS

    def test_requires_reset(self, robot: RobotConfig) -> None:
        planner = PurePursuitLocalPlanner()
        with pytest.raises(RuntimeError, match="reset"):
            planner.compute(None, None)  # type: ignore[arg-type]
