"""Tests for the pure-pursuit adapter (temporary follower)."""

from __future__ import annotations

import math

import pytest

from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_simulator.path_follower import PurePursuitConfig, PurePursuitFollower


def p(x: float, y: float) -> Point2D:
    return Point2D(x=x, y=y)


def state_at(x: float, y: float, theta: float = 0.0) -> RobotState:
    return RobotState(pose=Pose2D(x=x, y=y, theta=theta))


@pytest.fixture
def robot() -> RobotConfig:
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=2.0,
    )


class TestPurePursuit:
    def test_target_ahead_drives_forward(self, robot: RobotConfig) -> None:
        follower = PurePursuitFollower([p(0, 0), p(5, 0)], robot)
        action = follower.compute_action(state_at(0.0, 0.0))
        assert action.linear_velocity > 0.5
        assert abs(action.angular_velocity) < 1e-9

    def test_target_behind_turns_in_place(self, robot: RobotConfig) -> None:
        follower = PurePursuitFollower([p(-5, 0)], robot)
        action = follower.compute_action(state_at(0.0, 0.0, theta=0.0))
        assert action.linear_velocity == pytest.approx(0.0, abs=1e-9)
        assert abs(action.angular_velocity) == robot.max_angular_velocity

    def test_target_left_turns_left(self, robot: RobotConfig) -> None:
        follower = PurePursuitFollower([p(0, 5)], robot)
        action = follower.compute_action(state_at(0.0, 0.0, theta=0.0))
        assert action.angular_velocity > 0.0

    def test_slows_near_goal(self, robot: RobotConfig) -> None:
        follower = PurePursuitFollower([p(0, 0), p(0.4, 0)], robot)
        action = follower.compute_action(state_at(0.0, 0.0))
        assert 0.0 < action.linear_velocity < robot.max_linear_velocity / 2 + 1e-9

    def test_advances_past_visited_waypoints(self, robot: RobotConfig) -> None:
        follower = PurePursuitFollower([p(0, 0), p(1, 0), p(2, 0)], robot)
        action = follower.compute_action(state_at(0.9, 0.0))
        # Robot mid-path: nearest-waypoint advance must skip the start point
        # so the target is ahead, not behind.
        assert follower.target_index == 2
        assert action.linear_velocity > 0.0

    def test_deterministic(self, robot: RobotConfig) -> None:
        path = [p(0, 0), p(2, 1), p(4, 0)]
        first = PurePursuitFollower(path, robot).compute_action(state_at(0.5, 0.2, 0.1))
        second = PurePursuitFollower(path, robot).compute_action(state_at(0.5, 0.2, 0.1))
        assert first == second

    def test_empty_path_raises(self, robot: RobotConfig) -> None:
        with pytest.raises(ValueError, match="at least one point"):
            PurePursuitFollower([], robot)

    def test_config_validation(self) -> None:
        with pytest.raises(ValueError):
            PurePursuitConfig(lookahead_distance=0.0)

    def test_angular_velocity_clamped(self, robot: RobotConfig) -> None:
        follower = PurePursuitFollower([p(0, 5)], robot, PurePursuitConfig(heading_gain=100.0))
        action = follower.compute_action(state_at(0.0, 0.0))
        assert abs(action.angular_velocity) <= robot.max_angular_velocity

    def test_heading_scale_zero_when_perpendicular(self, robot: RobotConfig) -> None:
        # Target 90 degrees to the left: cos(pi/2) = 0 -> no forward motion.
        follower = PurePursuitFollower([p(0, 5)], robot)
        action = follower.compute_action(state_at(0.0, 0.0, theta=0.0))
        assert action.linear_velocity == pytest.approx(0.0, abs=1e-9)
        assert math.copysign(1.0, action.angular_velocity) == 1.0
