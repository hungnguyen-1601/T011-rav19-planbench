"""Tests for dynamic obstacle motion laws and their engine integration."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from planbench_schemas.dynamic import (
    DynamicObstacle,
    PeriodicMotion,
    RandomWalkMotion,
    SuddenStopMotion,
    WaypointMotion,
    position_at,
)
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig, SimAction
from planbench_schemas.scenario import Scenario
from planbench_simulator.engine import SimulationEngine


def p(x: float, y: float) -> Point2D:
    return Point2D(x=x, y=y)


class TestWaypointMotion:
    def obstacle(self, **kw) -> DynamicObstacle:
        defaults: dict = {
            "waypoints": (p(0, 0), p(10, 0)),
            "speed": 1.0,
            "loop": False,
        }
        defaults.update(kw)
        return DynamicObstacle(name="w", radius=0.3, motion=WaypointMotion(**defaults))

    def test_moves_at_the_configured_speed(self) -> None:
        obstacle = self.obstacle()
        assert position_at(obstacle, 0.0, 0) == p(0, 0)
        position = position_at(obstacle, 4.0, 0)
        assert position.x == pytest.approx(4.0)
        assert position.y == pytest.approx(0.0)

    def test_one_shot_motion_parks_at_the_end(self) -> None:
        obstacle = self.obstacle()
        assert position_at(obstacle, 100.0, 0).x == pytest.approx(10.0)

    def test_looping_returns_to_the_start(self) -> None:
        # Loop closes 10 m out and 10 m back = 20 m at 1 m/s.
        obstacle = self.obstacle(loop=True)
        assert position_at(obstacle, 20.0, 0).x == pytest.approx(0.0, abs=1e-9)
        assert position_at(obstacle, 15.0, 0).x == pytest.approx(5.0)

    def test_ping_pong_reverses_along_the_polyline(self) -> None:
        obstacle = self.obstacle(waypoints=(p(0, 0), p(4, 0), p(4, 3)), ping_pong=True)
        # Forward 4 + 3 = 7 m, then back 3 + 4 = 7 m -> period 14 s at 1 m/s.
        assert position_at(obstacle, 0.0, 0) == p(0, 0)
        assert position_at(obstacle, 14.0, 0).x == pytest.approx(0.0, abs=1e-9)
        midway_back = position_at(obstacle, 8.5, 0)
        assert midway_back.y == pytest.approx(1.5)  # descending the vertical leg

    def test_repeated_waypoint_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not repeat"):
            WaypointMotion(waypoints=(p(1, 1), p(1, 1)), speed=1.0)

    def test_deterministic(self) -> None:
        obstacle = self.obstacle()
        assert position_at(obstacle, 3.3, 7) == position_at(obstacle, 3.3, 7)


class TestPeriodicMotion:
    def obstacle(self) -> DynamicObstacle:
        return DynamicObstacle(
            name="crosser",
            radius=0.25,
            motion=PeriodicMotion(start=p(0, 0), end=p(0, 4), period=8.0),
        )

    def test_endpoints_at_half_period(self) -> None:
        obstacle = self.obstacle()
        assert position_at(obstacle, 0.0, 0).y == pytest.approx(0.0)
        assert position_at(obstacle, 4.0, 0).y == pytest.approx(4.0)
        assert position_at(obstacle, 8.0, 0).y == pytest.approx(0.0, abs=1e-9)

    def test_stays_between_the_endpoints(self) -> None:
        obstacle = self.obstacle()
        for step in range(0, 200):
            y = position_at(obstacle, step * 0.1, 0).y
            assert -1e-9 <= y <= 4.0 + 1e-9

    def test_phase_shifts_the_cycle(self) -> None:
        shifted = DynamicObstacle(
            name="c",
            radius=0.25,
            motion=PeriodicMotion(start=p(0, 0), end=p(0, 4), period=8.0, phase=math.pi),
        )
        assert position_at(shifted, 0.0, 0).y == pytest.approx(4.0)

    def test_identical_endpoints_rejected(self) -> None:
        with pytest.raises(ValidationError, match="distinct endpoints"):
            PeriodicMotion(start=p(1, 1), end=p(1, 1), period=4.0)


class TestRandomWalkMotion:
    def obstacle(self, seed_offset: int = 0) -> DynamicObstacle:
        return DynamicObstacle(
            name="walker",
            radius=0.2,
            motion=RandomWalkMotion(
                origin=p(5, 5),
                speed=0.5,
                change_interval=1.0,
                max_radius=2.0,
                seed_offset=seed_offset,
            ),
        )

    def test_same_seed_same_walk(self) -> None:
        obstacle = self.obstacle()
        first = [position_at(obstacle, t * 0.5, 42) for t in range(20)]
        second = [position_at(obstacle, t * 0.5, 42) for t in range(20)]
        assert first == second

    def test_different_seeds_differ(self) -> None:
        obstacle = self.obstacle()
        assert position_at(obstacle, 5.0, 1) != position_at(obstacle, 5.0, 2)

    def test_seed_offset_separates_obstacles(self) -> None:
        assert position_at(self.obstacle(0), 5.0, 7) != position_at(self.obstacle(1), 5.0, 7)

    def test_stays_near_the_origin(self) -> None:
        obstacle = self.obstacle()
        for seed in (1, 2, 3):
            for step in range(120):
                position = position_at(obstacle, step * 0.25, seed)
                # Reflection allows one step of overshoot beyond max_radius.
                overshoot = 0.5 * 1.0
                assert math.hypot(position.x - 5, position.y - 5) <= 2.0 + overshoot + 1e-9

    def test_position_independent_of_sampling_rate(self) -> None:
        """Sampling at t directly must match the incremental walk."""
        obstacle = self.obstacle()
        assert position_at(obstacle, 3.0, 9) == position_at(obstacle, 3.0, 9)


class TestSuddenStopMotion:
    def test_moves_then_parks(self) -> None:
        obstacle = DynamicObstacle(
            name="brake",
            radius=0.3,
            motion=SuddenStopMotion(start=p(0, 0), heading=0.0, speed=2.0, stop_time=3.0),
        )
        assert position_at(obstacle, 1.0, 0).x == pytest.approx(2.0)
        assert position_at(obstacle, 3.0, 0).x == pytest.approx(6.0)
        assert position_at(obstacle, 50.0, 0).x == pytest.approx(6.0)  # parked


class TestValidation:
    def test_negative_time_rejected(self) -> None:
        obstacle = DynamicObstacle(
            name="w", radius=0.3, motion=WaypointMotion(waypoints=(p(0, 0), p(1, 0)), speed=1.0)
        )
        with pytest.raises(ValueError, match="non-negative"):
            position_at(obstacle, -0.1, 0)

    def test_radius_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            DynamicObstacle(
                name="w",
                radius=0.0,
                motion=WaypointMotion(waypoints=(p(0, 0), p(1, 0)), speed=1.0),
            )


class TestEngineIntegration:
    def robot(self) -> RobotConfig:
        return RobotConfig(
            radius=0.3,
            max_linear_velocity=1.0,
            max_angular_velocity=2.0,
            max_linear_acceleration=1.0,
            max_angular_acceleration=3.0,
        )

    def scenario(self, **kw) -> Scenario:
        defaults: dict = {
            "name": "dynamic-test",
            "robot": self.robot(),
            "start_pose": Pose2D(x=2.5, y=5.5, theta=0.0),
            "goal_pose": Pose2D(x=12.5, y=5.5, theta=0.0),
            "goal_tolerance": 0.4,
            "timeout_seconds": 60.0,
            "simulation_dt": 0.05,
        }
        defaults.update(kw)
        return Scenario(**defaults)

    def test_moving_obstacle_causes_collision(self, bordered_map_factory) -> None:
        """A cart parked across the path is hit by a robot driving straight."""
        blocker = DynamicObstacle(
            name="cart",
            radius=0.5,
            motion=WaypointMotion(waypoints=(p(6.0, 5.5), p(6.0, 5.6)), speed=0.01, loop=False),
        )
        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(16, 12))
        engine.load_scenario(self.scenario(dynamic_obstacles=(blocker,)))
        engine.reset()
        while not engine.is_done():
            engine.step(SimAction(linear_velocity=1.0, angular_velocity=0.0))
        result = engine.get_result()
        assert result.status is EpisodeStatus.COLLISION
        assert "dynamic obstacle" in result.reason

    def test_obstacle_that_moves_away_does_not_collide(self, bordered_map_factory) -> None:
        """Same geometry, but the obstacle clears the lane in time."""
        mover = DynamicObstacle(
            name="crosser",
            radius=0.4,
            motion=WaypointMotion(waypoints=(p(6.0, 5.5), p(6.0, 10.0)), speed=3.0, loop=False),
        )
        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(16, 12))
        engine.load_scenario(self.scenario(dynamic_obstacles=(mover,)))
        engine.reset()
        while not engine.is_done():
            engine.step(SimAction(linear_velocity=1.0, angular_velocity=0.0))
        assert engine.get_result().status is EpisodeStatus.SUCCESS

    def test_start_inside_a_dynamic_obstacle_is_rejected(self, bordered_map_factory) -> None:
        blocker = DynamicObstacle(
            name="cart",
            radius=0.5,
            motion=WaypointMotion(waypoints=(p(2.5, 5.5), p(3.0, 5.5)), speed=0.1, loop=False),
        )
        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(16, 12))
        with pytest.raises(ValueError, match="collides"):
            engine.load_scenario(self.scenario(dynamic_obstacles=(blocker,)))

    def test_trajectory_records_obstacle_snapshots(self, bordered_map_factory) -> None:
        mover = DynamicObstacle(
            name="crosser",
            radius=0.4,
            motion=PeriodicMotion(start=p(8.0, 2.0), end=p(8.0, 9.0), period=6.0),
        )
        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(16, 12))
        engine.load_scenario(self.scenario(dynamic_obstacles=(mover,), timeout_seconds=2.0))
        engine.reset()
        for _ in range(10):
            engine.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
        trajectory = engine.get_state(), engine._trajectory  # noqa: SLF001 - white-box check
        samples = trajectory[1]
        assert all(len(point.obstacles) == 1 for point in samples)
        assert samples[0].obstacles[0].name == "crosser"
        # The obstacle actually moves between samples.
        assert samples[0].obstacles[0].y != samples[-1].obstacles[0].y

    def test_lidar_sees_the_moving_obstacle(self, bordered_map_factory) -> None:
        """The scan must shorten where a dynamic obstacle now stands.

        Ranges follow the rasterized cell boundary, not the exact circle:
        obstacles are burned into the sensor grid at map resolution (1 m
        here), so a circle at x=5.5 first blocks the cell spanning
        x in [4, 5] and the forward ray stops at 1.5 m from x=2.5.
        """
        mover = DynamicObstacle(
            name="crosser",
            radius=0.6,
            motion=WaypointMotion(waypoints=(p(5.5, 5.5), p(5.6, 5.5)), speed=0.01, loop=False),
        )
        map_data = bordered_map_factory(16, 12)

        clear = SimulationEngine()
        clear.load_map(map_data)
        clear.load_scenario(self.scenario())
        clear.reset()
        clear_scan = clear.get_observation().lidar_ranges

        blocked = SimulationEngine()
        blocked.load_map(map_data)
        blocked.load_scenario(self.scenario(dynamic_obstacles=(mover,)))
        blocked.reset()
        blocked_scan = blocked.get_observation().lidar_ranges

        forward = len(blocked_scan) // 2  # ray straight ahead (+x)
        assert blocked_scan[forward] < clear_scan[forward]
        assert blocked_scan[forward] == pytest.approx(1.5, abs=1e-9)

    def test_lidar_tracks_the_obstacle_as_it_moves(self, bordered_map_factory) -> None:
        """The scan is rebuilt per observation, so it follows the motion."""
        crosser = DynamicObstacle(
            name="crosser",
            radius=0.5,
            motion=PeriodicMotion(start=p(6.0, 5.5), end=p(6.0, 11.0), period=8.0),
        )
        engine = SimulationEngine()
        engine.load_map(bordered_map_factory(16, 12))
        engine.load_scenario(self.scenario(dynamic_obstacles=(crosser,)))
        engine.reset()
        forward = len(engine.get_observation().lidar_ranges) // 2
        blocked_at_start = engine.get_observation().lidar_ranges[forward]
        # Let the obstacle climb out of the robot's lane (quarter period).
        for _ in range(40):
            engine.step(SimAction(linear_velocity=0.0, angular_velocity=0.0))
        cleared = engine.get_observation().lidar_ranges[forward]
        assert cleared > blocked_at_start

    def test_episode_is_deterministic_with_a_random_walker(self, bordered_map_factory) -> None:
        walker = DynamicObstacle(
            name="walker",
            radius=0.3,
            motion=RandomWalkMotion(
                origin=p(8.0, 7.0), speed=0.6, change_interval=0.5, max_radius=2.0
            ),
        )
        trajectories = []
        for _ in range(2):
            engine = SimulationEngine()
            engine.load_map(bordered_map_factory(16, 12))
            engine.load_scenario(
                self.scenario(dynamic_obstacles=(walker,), random_seed=123, timeout_seconds=5.0)
            )
            engine.reset()
            while not engine.is_done():
                engine.step(SimAction(linear_velocity=0.8, angular_velocity=0.0))
            trajectories.append(engine.get_result().trajectory)
        assert trajectories[0] == trajectories[1]

    def test_different_seeds_change_a_random_walker(self, bordered_map_factory) -> None:
        walker = DynamicObstacle(
            name="walker",
            radius=0.3,
            motion=RandomWalkMotion(
                origin=p(8.0, 7.0), speed=0.6, change_interval=0.5, max_radius=2.0
            ),
        )
        positions = []
        for seed in (1, 2):
            engine = SimulationEngine()
            engine.load_map(bordered_map_factory(16, 12))
            engine.load_scenario(
                self.scenario(dynamic_obstacles=(walker,), random_seed=seed, timeout_seconds=3.0)
            )
            engine.reset()
            while not engine.is_done():
                engine.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
            positions.append(engine.get_result().trajectory[-1].obstacles[0].x)
        assert positions[0] != positions[1]
