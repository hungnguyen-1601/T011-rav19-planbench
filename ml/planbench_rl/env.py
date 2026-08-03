"""Gymnasium environment wrapping the PlanBench simulator.

The environment is a *thin adapter*: A* plans the global path, the
simulator owns physics and termination, and this class only translates
between Gym's arrays and the domain objects. No navigation logic lives
here (core-first).

Action space: ``Box([-1, -1], [1, 1])`` — normalized (v, omega) scaled to
the robot's limits. Normalized actions keep the policy independent of a
particular robot's speed, and SB3's default action noise assumes roughly
unit scale.

Safety: actions are checked for NaN/inf and clipped before they reach
the simulator (spec section 13). An invalid action becomes a full stop
and is counted, never silently zeroed.

Determinism: ``reset(seed=...)`` picks the scenario seed, which drives
every stochastic element (dynamic obstacles). Same seed, same episode.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from planbench_rl.observation import ObservationConfig, encode
from planbench_rl.rewards import RewardConfig, step_reward
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Point2D, euclidean_distance
from planbench_schemas.map import MapData
from planbench_schemas.robot import SimAction
from planbench_schemas.scenario import Scenario
from planbench_simulator.collision import clearance_to_obstacles
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.nav_stack import plan_global_path

ScenarioSource = Sequence[tuple[MapData, Scenario]]


class PlanBenchNavEnv(gym.Env):
    """Navigate to a goal using LiDAR plus an A* global path.

    One episode = one scenario run. With several scenarios supplied, the
    environment cycles through them deterministically by episode index,
    which is what makes curriculum training reproducible.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        scenarios: ScenarioSource,
        observation_config: ObservationConfig | None = None,
        reward_config: RewardConfig | None = None,
        max_episode_steps: int | None = None,
    ) -> None:
        super().__init__()
        if not scenarios:
            raise ValueError("PlanBenchNavEnv needs at least one (map, scenario) pair")
        self._scenarios = list(scenarios)
        self._observation_config = observation_config or ObservationConfig()
        self._reward_config = reward_config or RewardConfig()
        self._max_episode_steps = max_episode_steps

        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(self._observation_config.size,), dtype=np.float32
        )
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)

        self._engine = SimulationEngine()
        self._scenario: Scenario | None = None
        self._path: tuple[Point2D, ...] = ()
        self._raw_grid: OccupancyGrid | None = None
        self._episode_index = 0
        self._steps = 0
        self._previous_goal_distance = 0.0
        self._previous_angular_velocity = 0.0
        self._invalid_actions = 0
        self._reward_total = 0.0

    # -- Gym API -------------------------------------------------------

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        index = (options or {}).get("scenario_index")
        if index is None:
            index = self._episode_index % len(self._scenarios)
        map_data, scenario = self._scenarios[index]
        episode_seed = seed if seed is not None else scenario.random_seed
        scenario = scenario.model_copy(update={"random_seed": int(episode_seed)})

        plan, raw_grid = plan_global_path(map_data, scenario)
        if not plan.success:
            raise RuntimeError(
                f"scenario {scenario.name!r} has no global path: {plan.failure_reason}"
            )
        self._path = plan.path
        self._raw_grid = raw_grid
        self._scenario = scenario

        self._engine.load_map(map_data)
        self._engine.load_scenario(scenario)
        self._engine.reset()
        self._episode_index += 1
        self._steps = 0
        self._invalid_actions = 0
        self._reward_total = 0.0
        self._previous_angular_velocity = 0.0
        self._previous_goal_distance = euclidean_distance(
            scenario.start_pose.position, scenario.goal_pose.position
        )
        return self._observation(), self._info(EpisodeStatus.RUNNING)

    def step(self, action):
        if self._scenario is None:
            raise RuntimeError("reset() must be called before step()")
        scenario = self._scenario
        command, valid = self._to_command(action)
        if not valid:
            self._invalid_actions += 1

        state = self._engine.step(command)
        self._steps += 1
        status = self._engine.episode_status

        goal_distance = euclidean_distance(state.pose.position, scenario.goal_pose.position)
        progress = self._previous_goal_distance - goal_distance
        self._previous_goal_distance = goal_distance

        breakdown = step_reward(
            self._reward_config,
            progress_metres=progress,
            path_deviation=self._path_deviation(state.pose.position),
            clearance=self._clearance(state.pose.position),
            linear_velocity=command.linear_velocity,
            angular_velocity=command.angular_velocity,
            previous_angular_velocity=self._previous_angular_velocity,
            status=status,
        )
        self._previous_angular_velocity = command.angular_velocity
        self._reward_total += breakdown.total

        terminated = self._engine.is_done() and status is not EpisodeStatus.TIMEOUT
        truncated = status is EpisodeStatus.TIMEOUT or (
            self._max_episode_steps is not None and self._steps >= self._max_episode_steps
        )
        info = self._info(status)
        info["reward_components"] = breakdown.components
        return self._observation(), breakdown.total, terminated, truncated, info

    # -- internals -----------------------------------------------------

    def _to_command(self, action) -> tuple[SimAction, bool]:
        """Validate, clip and denormalize the policy output.

        A NaN or infinite action means the policy is broken; the safe
        response is a full stop, recorded in ``info`` so a training run
        cannot hide it.
        """
        assert self._scenario is not None
        robot = self._scenario.robot
        array = np.asarray(action, dtype=np.float64).reshape(-1)
        if array.size < 2 or not np.all(np.isfinite(array)):
            return SimAction(linear_velocity=0.0, angular_velocity=0.0), False
        normalized = np.clip(array[:2], -1.0, 1.0)
        return (
            SimAction(
                linear_velocity=float(normalized[0]) * robot.max_linear_velocity,
                angular_velocity=float(normalized[1]) * robot.max_angular_velocity,
            ),
            True,
        )

    def _observation(self) -> np.ndarray:
        assert self._scenario is not None
        return encode(
            self._engine.get_observation(),
            self._path,
            self._scenario.robot,
            self._scenario.lidar.max_range,
            self._observation_config,
        )

    def _clearance(self, position: Point2D) -> float:
        assert self._scenario is not None and self._raw_grid is not None
        value = clearance_to_obstacles(
            position,
            self._scenario.robot.radius,
            self._scenario.static_obstacles,
            self._raw_grid,
        )
        return value if math.isfinite(value) else self._observation_config.observation_range

    def _path_deviation(self, position: Point2D) -> float:
        from planbench_rl.observation import cross_track_error

        return cross_track_error(self._path, position)

    def _info(self, status: EpisodeStatus) -> dict:
        return {
            "status": status.value,
            "steps": self._steps,
            "scenario": self._scenario.name if self._scenario else "",
            "invalid_actions": self._invalid_actions,
            "episode_reward": self._reward_total,
            "is_success": status is EpisodeStatus.SUCCESS,
            "observation_version": self._observation_config.version,
            "reward_version": self._reward_config.version,
        }
