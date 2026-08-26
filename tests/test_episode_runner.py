"""End-to-end tests: A* plan + pure-pursuit follow + engine episode."""

from __future__ import annotations

import pytest

from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.episode_runner import run_episode


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
        "name": "runner-test",
        "robot": robot,
        "start_pose": Pose2D(x=2.5, y=2.5, theta=0.0),
        "goal_pose": Pose2D(x=9.5, y=9.5, theta=0.0),
        "goal_tolerance": 0.3,
        "timeout_seconds": 120.0,
        "simulation_dt": 0.05,
    }
    defaults.update(overrides)
    return Scenario(**defaults)


class TestEpisodeRunner:
    def test_open_map_success(self, bordered_map_factory, robot: RobotConfig) -> None:
        run = run_episode(bordered_map_factory(12, 12), make_scenario(robot))
        assert run.plan.success
        assert run.result.status is EpisodeStatus.SUCCESS
        assert run.metrics.success
        assert run.metrics.trajectory_length > 5.0
        assert run.metrics.min_clearance is not None and run.metrics.min_clearance > 0.0
        assert run.metrics.path_efficiency is not None

    def test_detour_around_wall_without_collision(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        # Vertical wall at col 7 (rows 1..9) with a passage near row 11.
        map_data = bordered_map_factory(14, 14, occupied=tuple((row, 7) for row in range(1, 10)))
        scenario = make_scenario(
            robot,
            start_pose=Pose2D(x=2.5, y=2.5, theta=0.0),
            goal_pose=Pose2D(x=11.5, y=2.5, theta=0.0),
        )
        run = run_episode(map_data, scenario)
        assert run.plan.success
        assert run.result.status is EpisodeStatus.SUCCESS
        # The detour is much longer than the straight-line distance (9 m).
        assert run.metrics.trajectory_length > 12.0
        assert run.metrics.min_clearance is not None and run.metrics.min_clearance > 0.0

    def test_no_global_path(self, bordered_map_factory, robot: RobotConfig) -> None:
        map_data = bordered_map_factory(12, 12, occupied=tuple((row, 6) for row in range(12)))
        run = run_episode(
            map_data,
            make_scenario(robot, goal_pose=Pose2D(x=9.5, y=2.5, theta=0.0)),
        )
        assert not run.plan.success
        assert run.result.status is EpisodeStatus.NO_GLOBAL_PATH
        assert run.result.trajectory == ()
        assert not run.metrics.success

    def test_deterministic_end_to_end(self, bordered_map_factory, robot: RobotConfig) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        first = run_episode(map_data, scenario)
        second = run_episode(map_data, scenario)
        assert first.plan.path == second.plan.path
        assert first.result.trajectory == second.result.trajectory
        assert first.metrics.trajectory_length == second.metrics.trajectory_length
