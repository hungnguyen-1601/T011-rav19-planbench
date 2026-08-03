"""Tests for the DWA local planner: safety, limits, determinism, costs."""

from __future__ import annotations

import math

import pytest

from planbench_planning import DWAConfig, DWAPlanner
from planbench_schemas.episode import Observation
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_schemas.sensor import LidarConfig
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.lidar import scan

MAX_RANGE = 5.0
LIDAR = LidarConfig(num_rays=72, max_range=MAX_RANGE)


@pytest.fixture
def robot() -> RobotConfig:
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=3.0,
    )


def observation_at(
    grid: OccupancyGrid, pose: Pose2D, goal: Point2D, time: float = 0.0
) -> Observation:
    bearing = math.atan2(goal.y - pose.y, goal.x - pose.x) - pose.theta
    return Observation(
        time=time,
        pose=pose,
        linear_velocity=0.0,
        angular_velocity=0.0,
        goal_distance=math.hypot(goal.x - pose.x, goal.y - pose.y),
        goal_bearing=math.atan2(math.sin(bearing), math.cos(bearing)),
        lidar_ranges=scan(grid, pose, LIDAR),
    )


def state_at(x: float, y: float, theta: float = 0.0, v: float = 0.0, w: float = 0.0) -> RobotState:
    return RobotState(pose=Pose2D(x=x, y=y, theta=theta), linear_velocity=v, angular_velocity=w)


class TestDWABasics:
    def test_drives_toward_the_goal_in_open_space(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        grid = OccupancyGrid(bordered_map_factory(20, 20))
        planner = DWAPlanner()
        goal = Point2D(x=15.0, y=10.0)
        planner.reset([Point2D(x=5.0, y=10.0), goal], robot)
        state = state_at(5.0, 10.0)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        assert decision.action.linear_velocity > 0.0
        assert abs(decision.action.angular_velocity) < 0.5  # goal is straight ahead
        assert decision.predicted_trajectory
        assert set(decision.cost_components) == {
            "goal",
            "heading",
            "path",
            "clearance",
            "velocity",
            "smoothness",
            "oscillation",
        }
        assert decision.latency_seconds >= 0.0

    def test_turns_toward_a_goal_to_the_left(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        grid = OccupancyGrid(bordered_map_factory(20, 20))
        planner = DWAPlanner()
        goal = Point2D(x=10.0, y=16.0)
        planner.reset([Point2D(x=10.0, y=10.0), goal], robot)
        state = state_at(10.0, 10.0, theta=0.0)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        assert decision.action.angular_velocity > 0.0

    def test_requires_reset(self, robot: RobotConfig, bordered_map_factory) -> None:
        grid = OccupancyGrid(bordered_map_factory(20, 20))
        planner = DWAPlanner()
        state = state_at(5.0, 5.0)
        with pytest.raises(RuntimeError, match="reset"):
            planner.compute(state, observation_at(grid, state.pose, Point2D(x=6.0, y=5.0)))

    def test_reset_rejects_empty_path(self, robot: RobotConfig) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            DWAPlanner().reset([], robot)

    def test_name_identifies_the_algorithm(self) -> None:
        assert DWAPlanner().name == "dwa"


class TestDWASafety:
    def test_respects_velocity_limits(self, bordered_map_factory, robot: RobotConfig) -> None:
        grid = OccupancyGrid(bordered_map_factory(20, 20))
        planner = DWAPlanner()
        goal = Point2D(x=18.0, y=10.0)
        planner.reset([Point2D(x=5.0, y=10.0), goal], robot)
        state = state_at(5.0, 10.0, v=robot.max_linear_velocity)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        assert abs(decision.action.linear_velocity) <= robot.max_linear_velocity + 1e-12
        assert abs(decision.action.angular_velocity) <= robot.max_angular_velocity + 1e-12

    def test_respects_acceleration_limits(self, bordered_map_factory, robot: RobotConfig) -> None:
        config = DWAConfig(control_period=0.1)
        grid = OccupancyGrid(bordered_map_factory(20, 20))
        planner = DWAPlanner(config)
        goal = Point2D(x=18.0, y=10.0)
        planner.reset([Point2D(x=5.0, y=10.0), goal], robot)
        state = state_at(5.0, 10.0, v=0.0, w=0.0)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        max_dv = robot.max_linear_acceleration * config.control_period
        max_dw = robot.max_angular_acceleration * config.control_period
        assert decision.action.linear_velocity <= max_dv + 1e-12
        assert abs(decision.action.angular_velocity) <= max_dw + 1e-12

    def test_no_forward_command_into_a_close_wall(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        """A wall 0.5 m ahead must not be driven into at speed."""
        # Wall column at col 11 spans x in [11, 12]; robot centre at x = 10.5.
        grid = OccupancyGrid(
            bordered_map_factory(20, 20, occupied=tuple((row, 11) for row in range(1, 19)))
        )
        planner = DWAPlanner()
        goal = Point2D(x=18.0, y=10.0)  # goal is behind the wall
        planner.reset([Point2D(x=10.5, y=10.0), goal], robot)
        state = state_at(10.5, 10.0, theta=0.0, v=0.5)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        # Any forward motion must keep the rollout clear of the wall; the
        # planner is free to stop or turn, but not to charge ahead.
        for point in decision.predicted_trajectory:
            assert point.x < 11.0 - robot.radius + 1e-9, "predicted path enters the wall"

    def test_rotating_in_place_stays_available_in_a_pocket(
        self, map_factory, robot: RobotConfig
    ) -> None:
        """Walls 0.5 m away block driving forward but not turning."""
        cells = tuple(
            (row, col)
            for row in range(9, 12)
            for col in range(9, 12)
            if not (row == 10 and col == 10)
        )
        grid = OccupancyGrid(map_factory(20, 20, occupied=cells))
        planner = DWAPlanner()
        goal = Point2D(x=18.0, y=10.0)
        planner.reset([Point2D(x=10.5, y=10.5), goal], robot)
        state = state_at(10.5, 10.5, v=0.0)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        assert decision.failure_reason == ""
        # A command is issued, but it must creep at most: the chosen speed
        # is far below the reachable maximum for this control period.
        max_reachable = robot.max_linear_acceleration * DWAConfig().control_period
        assert decision.action.linear_velocity < 0.25 * max_reachable
        # Safety invariant: the whole rollout keeps radius + margin from
        # the pocket walls (free cell spans [10, 11] x [10, 11]).
        keep_out = robot.radius + DWAConfig().safety_margin
        for point in decision.predicted_trajectory:
            assert 10.0 + keep_out <= point.x <= 11.0 - keep_out
            assert 10.0 + keep_out <= point.y <= 11.0 - keep_out

    def test_stops_when_every_candidate_collides(self, map_factory, robot: RobotConfig) -> None:
        """Pocket narrower than the robot -> stop command plus a reason."""
        # 0.25 m cells: the single free cell is far smaller than the
        # 0.3 m robot radius, so even holding position is unsafe.
        cells = tuple(
            (row, col)
            for row in range(9, 12)
            for col in range(9, 12)
            if not (row == 10 and col == 10)
        )
        grid = OccupancyGrid(map_factory(20, 20, resolution=0.25, occupied=cells))
        planner = DWAPlanner()
        goal = Point2D(x=4.0, y=2.625)
        planner.reset([Point2D(x=2.625, y=2.625), goal], robot)
        state = state_at(2.625, 2.625, v=0.0)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        assert decision.action.linear_velocity == 0.0
        assert decision.action.angular_velocity == 0.0
        assert "collide" in decision.failure_reason
        assert decision.predicted_trajectory == ()


class TestDWADeterminism:
    def test_identical_inputs_identical_commands(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        grid = OccupancyGrid(bordered_map_factory(20, 20, occupied=((10, 12), (11, 12))))
        goal = Point2D(x=16.0, y=10.0)
        path = [Point2D(x=5.0, y=10.0), goal]
        state = state_at(5.0, 10.0, theta=0.1, v=0.4, w=-0.2)
        observation = observation_at(grid, state.pose, goal)

        first = DWAPlanner()
        first.reset(path, robot)
        second = DWAPlanner()
        second.reset(path, robot)
        assert first.compute(state, observation).action == second.compute(state, observation).action

    def test_repeated_rollouts_are_stable(self, bordered_map_factory, robot: RobotConfig) -> None:
        grid = OccupancyGrid(bordered_map_factory(20, 20))
        goal = Point2D(x=16.0, y=10.0)
        actions = []
        for _ in range(3):
            planner = DWAPlanner()
            planner.reset([Point2D(x=5.0, y=10.0), goal], robot)
            state = state_at(5.0, 10.0)
            for _ in range(5):
                decision = planner.compute(state, observation_at(grid, state.pose, goal))
                actions.append((decision.action.linear_velocity, decision.action.angular_velocity))
        assert actions[0:5] == actions[5:10] == actions[10:15]


class TestDWACostComponents:
    def test_clearance_cost_higher_near_obstacles(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        # Wall column 11 spans x in [11, 12]: 0.5 m from the robot centre,
        # inside the 1.0 m clearance_cap where the cost is still graded.
        open_grid = OccupancyGrid(bordered_map_factory(20, 20))
        tight_grid = OccupancyGrid(
            bordered_map_factory(20, 20, occupied=tuple((row, 11) for row in range(1, 19)))
        )
        goal = Point2D(x=16.0, y=10.0)

        def clearance_cost(grid: OccupancyGrid) -> float:
            planner = DWAPlanner()
            planner.reset([Point2D(x=10.5, y=10.0), goal], robot)
            state = state_at(10.5, 10.0)
            return planner.compute(state, observation_at(grid, state.pose, goal)).cost_components[
                "clearance"
            ]

        assert clearance_cost(tight_grid) > clearance_cost(open_grid)

    def test_weights_are_configurable(self, bordered_map_factory, robot: RobotConfig) -> None:
        grid = OccupancyGrid(bordered_map_factory(20, 20))
        goal = Point2D(x=16.0, y=10.0)
        planner = DWAPlanner(DWAConfig(weight_velocity=0.0))
        planner.reset([Point2D(x=5.0, y=10.0), goal], robot)
        state = state_at(5.0, 10.0)
        decision = planner.compute(state, observation_at(grid, state.pose, goal))
        assert decision.cost_components["velocity"] == 0.0
