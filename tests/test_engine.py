"""Tests for the SimulationEngine lifecycle and termination logic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig, SimAction
from planbench_schemas.scenario import Scenario
from planbench_simulator.engine import EngineState, SimulationEngine

STRAIGHT = SimAction(linear_velocity=1.0, angular_velocity=0.0)
HALT = SimAction(linear_velocity=0.0, angular_velocity=0.0)


def make_scenario(robot: RobotConfig, **overrides) -> Scenario:
    defaults: dict = {
        "name": "engine-test",
        "robot": robot,
        "start_pose": Pose2D(x=2.5, y=2.5, theta=0.0),
        "goal_pose": Pose2D(x=7.5, y=2.5, theta=0.0),
        "goal_tolerance": 0.3,
        "timeout_seconds": 30.0,
        "simulation_dt": 0.05,
    }
    defaults.update(overrides)
    return Scenario(**defaults)


def run_until_done(engine: SimulationEngine, action: SimAction, max_steps: int = 10000) -> None:
    steps = 0
    while not engine.is_done():
        engine.step(action)
        steps += 1
        assert steps < max_steps, "episode did not terminate"


@pytest.fixture
def ready_engine(map_factory, robot_config: RobotConfig) -> SimulationEngine:
    engine = SimulationEngine()
    engine.load_map(map_factory(10, 10))
    engine.load_scenario(make_scenario(robot_config))
    engine.reset()
    return engine


class TestScenarioSchema:
    def test_dt_must_be_below_timeout(self, robot_config: RobotConfig) -> None:
        with pytest.raises(ValidationError, match="simulation_dt"):
            make_scenario(robot_config, simulation_dt=2.0, timeout_seconds=1.0)

    def test_start_must_differ_from_goal(self, robot_config: RobotConfig) -> None:
        with pytest.raises(ValidationError, match="must differ"):
            make_scenario(robot_config, goal_pose=Pose2D(x=2.5, y=2.5, theta=1.0))


class TestSetupValidation:
    def test_scenario_before_map_raises(self, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        with pytest.raises(RuntimeError, match="load_map"):
            engine.load_scenario(make_scenario(robot_config))

    def test_start_outside_map_rejected(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(5, 5))
        with pytest.raises(ValueError, match="outside the map"):
            engine.load_scenario(
                make_scenario(robot_config, start_pose=Pose2D(x=20.0, y=2.5, theta=0.0))
            )

    def test_start_in_obstacle_rejected(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(10, 10, occupied=((2, 2),)))
        with pytest.raises(ValueError, match="collides"):
            engine.load_scenario(make_scenario(robot_config))

    def test_step_before_reset_raises(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(10, 10))
        engine.load_scenario(make_scenario(robot_config))
        with pytest.raises(RuntimeError, match="cannot step"):
            engine.step(STRAIGHT)

    def test_get_result_before_done_raises(self, ready_engine: SimulationEngine) -> None:
        with pytest.raises(RuntimeError, match="finished or stopped"):
            ready_engine.get_result()


class TestTermination:
    def test_success(self, ready_engine: SimulationEngine) -> None:
        run_until_done(ready_engine, STRAIGHT)
        result = ready_engine.get_result()
        assert result.status is EpisodeStatus.SUCCESS
        assert result.elapsed_time > 0
        assert len(result.trajectory) == result.steps + 1
        assert result.events[-1].type == "success"

    def test_collision(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(10, 10, occupied=((2, 5),)))  # box [5,6]x[2,3]
        engine.load_scenario(make_scenario(robot_config, progress_time_window=25.0))
        engine.reset()
        run_until_done(engine, STRAIGHT)
        result = engine.get_result()
        assert result.status is EpisodeStatus.COLLISION
        # Robot stops at the box face: x + radius ~ 5.
        assert result.trajectory[-1].x <= 5.0 - robot_config.radius + 0.1

    def test_timeout(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(10, 10))
        engine.load_scenario(make_scenario(robot_config, timeout_seconds=0.5))
        engine.reset()
        run_until_done(engine, HALT)
        result = engine.get_result()
        assert result.status is EpisodeStatus.TIMEOUT
        assert result.elapsed_time == pytest.approx(0.5, abs=0.06)

    def test_stuck(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(10, 10))
        engine.load_scenario(
            make_scenario(
                robot_config,
                timeout_seconds=30.0,
                stuck_time_window=0.3,
                stuck_min_displacement=0.05,
            )
        )
        engine.reset()
        run_until_done(engine, HALT)
        result = engine.get_result()
        assert result.status is EpisodeStatus.STUCK
        assert result.elapsed_time < 1.0

    def test_no_progress_while_circling(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(10, 10))
        engine.load_scenario(
            make_scenario(
                robot_config,
                start_pose=Pose2D(x=5.0, y=5.0, theta=0.0),
                goal_pose=Pose2D(x=8.0, y=5.0, theta=0.0),
                timeout_seconds=30.0,
                stuck_time_window=10.0,
                progress_time_window=1.0,
                progress_min_decrease=0.1,
            )
        )
        engine.reset()
        run_until_done(engine, SimAction(linear_velocity=1.0, angular_velocity=2.0))
        result = engine.get_result()
        assert result.status is EpisodeStatus.NO_PROGRESS
        assert result.elapsed_time < 10.0


class TestControls:
    def test_pause_blocks_step_and_resume_restores(self, ready_engine: SimulationEngine) -> None:
        ready_engine.step(STRAIGHT)
        ready_engine.pause()
        assert ready_engine.engine_state is EngineState.PAUSED
        with pytest.raises(RuntimeError, match="cannot step"):
            ready_engine.step(STRAIGHT)
        ready_engine.resume()
        ready_engine.step(STRAIGHT)

    def test_stop_marks_episode_stopped(self, ready_engine: SimulationEngine) -> None:
        ready_engine.step(STRAIGHT)
        ready_engine.stop()
        assert ready_engine.is_done()
        assert ready_engine.get_result().status is EpisodeStatus.STOPPED

    def test_reset_restarts(self, ready_engine: SimulationEngine) -> None:
        run_until_done(ready_engine, STRAIGHT)
        ready_engine.reset()
        assert ready_engine.engine_state is EngineState.RUNNING
        assert ready_engine.get_state().pose.x == 2.5
        assert ready_engine.time == 0.0


class TestObservation:
    def test_observation_contents(self, ready_engine: SimulationEngine) -> None:
        observation = ready_engine.get_observation()
        assert len(observation.lidar_ranges) == 72  # scenario default
        assert observation.goal_distance == pytest.approx(5.0, abs=1e-9)
        assert observation.goal_bearing == pytest.approx(0.0, abs=1e-9)  # goal dead ahead
        assert observation.time == 0.0

    def test_observation_before_reset_raises(self, map_factory, robot_config: RobotConfig) -> None:
        engine = SimulationEngine()
        engine.load_map(map_factory(10, 10))
        engine.load_scenario(make_scenario(robot_config))
        with pytest.raises(RuntimeError, match="reset"):
            engine.get_observation()


class TestDeterminism:
    def test_identical_runs_identical_trajectories(
        self, map_factory, robot_config: RobotConfig
    ) -> None:
        action = SimAction(linear_velocity=0.8, angular_velocity=0.3)
        trajectories = []
        for _ in range(2):
            engine = SimulationEngine()
            engine.load_map(map_factory(10, 10))
            engine.load_scenario(
                make_scenario(robot_config, timeout_seconds=2.0, progress_time_window=1.9)
            )
            engine.reset()
            while not engine.is_done():
                engine.step(action)
            trajectories.append(engine.get_result().trajectory)
        assert trajectories[0] == trajectories[1]
