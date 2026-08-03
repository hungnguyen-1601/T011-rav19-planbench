"""Deterministic single-episode simulation engine.

Lifecycle: ``load_map()`` → ``load_scenario()`` → ``reset()`` → repeated
``step(action)`` until ``is_done()``, then ``get_result()``.
``pause()/resume()/stop()`` control execution between steps.

Termination checks run after every step in a fixed priority order
(first match wins): collision > goal reached > timeout > stuck >
failure to progress.

Sensing note: LiDAR scans a grid with static shape obstacles rasterized
in (cell-resolution approximation) plus the current dynamic obstacles
rasterized per step; collision uses the raw grid plus exact geometry for
both static and dynamic obstacles.

Dynamic obstacles are pure functions of (spec, time, seed) — see
``planbench_schemas.dynamic`` — so an episode replays identically from
its seed. Their ground-truth poses are recorded in every trajectory
sample for replay and failure analysis, but planners only ever see them
through the LiDAR scan.
"""

from __future__ import annotations

import math
from collections import deque
from enum import StrEnum

from planbench_schemas.dynamic import position_at
from planbench_schemas.episode import (
    EpisodeEvent,
    EpisodeResult,
    EpisodeStatus,
    Observation,
    ObstacleSnapshot,
    TrajectoryPoint,
)
from planbench_schemas.geometry import EPS, Point2D, euclidean_distance, normalize_angle
from planbench_schemas.map import MapData
from planbench_schemas.robot import RobotState, SimAction
from planbench_schemas.scenario import CircleObstacle, Scenario
from planbench_simulator.collision import collides_with_grid, collides_with_obstacle
from planbench_simulator.grid import OccupancyGrid, rasterize_obstacles
from planbench_simulator.kinematics import step as kinematics_step
from planbench_simulator.lidar import scan


class EngineState(StrEnum):
    """Execution state of the engine (distinct from episode status)."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    STOPPED = "stopped"


class SimulationEngine:
    """Runs one episode of a scenario on a map. Deterministic."""

    def __init__(self) -> None:
        self._grid: OccupancyGrid | None = None
        self._sensor_grid: OccupancyGrid | None = None
        self._scenario: Scenario | None = None
        self._state = EngineState.IDLE
        self._status = EpisodeStatus.RUNNING
        self._reason = ""
        self._robot: RobotState | None = None
        self._time = 0.0
        self._steps = 0
        self._trajectory: list[TrajectoryPoint] = []
        self._events: list[EpisodeEvent] = []
        # (time, x, y, goal_distance) samples for stuck / progress windows.
        self._window: deque[tuple[float, float, float, float]] = deque()

    # -- setup ---------------------------------------------------------

    def load_map(self, map_data: MapData, unknown_as_occupied: bool = True) -> None:
        """Load a map; invalidates any previously loaded scenario."""
        self._grid = OccupancyGrid(map_data, unknown_as_occupied)
        self._sensor_grid = None
        self._scenario = None
        self._state = EngineState.IDLE

    def load_scenario(self, scenario: Scenario) -> None:
        """Validate the scenario against the loaded map and store it."""
        if self._grid is None:
            raise RuntimeError("load_map() must be called before load_scenario()")
        radius = scenario.robot.radius
        for label, pose in (("start", scenario.start_pose), ("goal", scenario.goal_pose)):
            if not self._grid.is_inside(pose.x, pose.y):
                raise ValueError(f"{label} pose ({pose.x}, {pose.y}) is outside the map")
            initial_dynamic = _dynamic_circles(scenario, time=0.0)
            if (
                collides_with_grid(pose.position, radius, self._grid)
                or any(
                    collides_with_obstacle(pose.position, radius, obstacle)
                    for obstacle in scenario.static_obstacles
                )
                or any(
                    collides_with_obstacle(pose.position, radius, circle)
                    for circle in initial_dynamic
                )
            ):
                raise ValueError(f"{label} pose ({pose.x}, {pose.y}) collides with an obstacle")
        sensor_map = (
            rasterize_obstacles(self._grid.map_data, scenario.static_obstacles)
            if scenario.static_obstacles
            else self._grid.map_data
        )
        self._sensor_grid = OccupancyGrid(sensor_map, self._grid.unknown_as_occupied)
        self._scenario = scenario
        self._state = EngineState.IDLE

    def reset(self) -> None:
        """Start (or restart) the episode from the scenario's start pose."""
        if self._grid is None or self._scenario is None:
            raise RuntimeError("load_map() and load_scenario() must be called before reset()")
        scenario = self._scenario
        self._robot = RobotState(pose=scenario.start_pose)
        self._time = 0.0
        self._steps = 0
        self._status = EpisodeStatus.RUNNING
        self._reason = ""
        self._trajectory = [self._trajectory_point()]
        self._events = []
        self._window = deque(
            [(0.0, scenario.start_pose.x, scenario.start_pose.y, self._goal_distance())]
        )
        self._state = EngineState.RUNNING

    # -- stepping ------------------------------------------------------

    def step(self, action: SimAction) -> RobotState:
        """Advance one ``simulation_dt``; returns the new robot state."""
        if self._state is not EngineState.RUNNING:
            raise RuntimeError(f"cannot step: engine state is {self._state.value}")
        assert self._scenario is not None and self._robot is not None and self._grid is not None
        scenario = self._scenario
        dt = scenario.simulation_dt

        self._robot = kinematics_step(self._robot, action, scenario.robot, dt)
        self._time += dt
        self._steps += 1
        self._trajectory.append(self._trajectory_point())

        self._check_termination()
        self._record_window_sample()
        return self._robot

    def _check_termination(self) -> None:
        assert self._scenario is not None and self._robot is not None and self._grid is not None
        scenario = self._scenario
        center = self._robot.pose.position
        goal_distance = self._goal_distance()

        dynamic = self._dynamic_now()
        hit_dynamic = next(
            (
                circle
                for circle in dynamic
                if collides_with_obstacle(center, scenario.robot.radius, circle)
            ),
            None,
        )
        if (
            collides_with_grid(center, scenario.robot.radius, self._grid)
            or any(
                collides_with_obstacle(center, scenario.robot.radius, obstacle)
                for obstacle in scenario.static_obstacles
            )
            or hit_dynamic is not None
        ):
            kind = "dynamic obstacle" if hit_dynamic is not None else "static obstacle"
            self._terminate(
                EpisodeStatus.COLLISION,
                f"collision with {kind} at ({center.x:.3f}, {center.y:.3f}) "
                f"after {self._time:.2f}s",
            )
        elif goal_distance <= scenario.goal_tolerance:
            self._terminate(
                EpisodeStatus.SUCCESS,
                f"goal reached (distance {goal_distance:.3f} m) after {self._time:.2f}s",
            )
        elif self._time + EPS >= scenario.timeout_seconds:
            self._terminate(EpisodeStatus.TIMEOUT, f"timeout after {scenario.timeout_seconds:.2f}s")
        else:
            reference = self._sample_at_age(scenario.stuck_time_window)
            if reference is not None:
                _, ref_x, ref_y, _ = reference
                displacement = math.hypot(center.x - ref_x, center.y - ref_y)
                if displacement < scenario.stuck_min_displacement:
                    self._terminate(
                        EpisodeStatus.STUCK,
                        f"moved only {displacement:.3f} m in the last "
                        f"{scenario.stuck_time_window:.1f}s",
                    )
                    return
            reference = self._sample_at_age(scenario.progress_time_window)
            if reference is not None and self._status is EpisodeStatus.RUNNING:
                _, _, _, ref_goal_distance = reference
                if ref_goal_distance - goal_distance < scenario.progress_min_decrease:
                    self._terminate(
                        EpisodeStatus.NO_PROGRESS,
                        f"goal distance shrank by only "
                        f"{ref_goal_distance - goal_distance:.3f} m in the last "
                        f"{scenario.progress_time_window:.1f}s",
                    )

    def _terminate(self, status: EpisodeStatus, reason: str) -> None:
        self._status = status
        self._reason = reason
        self._events.append(EpisodeEvent(time=self._time, type=status.value, message=reason))
        self._state = EngineState.FINISHED

    def _record_window_sample(self) -> None:
        assert self._scenario is not None and self._robot is not None
        scenario = self._scenario
        self._window.append(
            (self._time, self._robot.pose.x, self._robot.pose.y, self._goal_distance())
        )
        max_age = max(scenario.stuck_time_window, scenario.progress_time_window)
        while len(self._window) > 1 and self._window[1][0] <= self._time - max_age:
            self._window.popleft()

    def _sample_at_age(self, age: float) -> tuple[float, float, float, float] | None:
        """Latest recorded sample at least ``age`` seconds old, if any."""
        cutoff = self._time - age + EPS
        candidate = None
        for sample in self._window:
            if sample[0] <= cutoff:
                candidate = sample
            else:
                break
        return candidate

    # -- queries -------------------------------------------------------

    def get_state(self) -> RobotState:
        if self._robot is None:
            raise RuntimeError("reset() must be called before get_state()")
        return self._robot

    def get_observation(self) -> Observation:
        """Local-planner view: LiDAR + goal geometry + own velocities."""
        if self._robot is None or self._scenario is None or self._sensor_grid is None:
            raise RuntimeError("reset() must be called before get_observation()")
        pose = self._robot.pose
        goal = self._scenario.goal_pose
        bearing = normalize_angle(math.atan2(goal.y - pose.y, goal.x - pose.x) - pose.theta)
        return Observation(
            time=self._time,
            pose=pose,
            linear_velocity=self._robot.linear_velocity,
            angular_velocity=self._robot.angular_velocity,
            goal_distance=self._goal_distance(),
            goal_bearing=bearing,
            lidar_ranges=scan(self._sensor_grid_now(), pose, self._scenario.lidar),
        )

    def is_done(self) -> bool:
        return self._state in (EngineState.FINISHED, EngineState.STOPPED)

    def get_result(self) -> EpisodeResult:
        if not self.is_done():
            raise RuntimeError("get_result() requires a finished or stopped episode")
        return EpisodeResult(
            status=self._status,
            reason=self._reason,
            elapsed_time=self._time,
            steps=self._steps,
            trajectory=tuple(self._trajectory),
            events=tuple(self._events),
        )

    @property
    def engine_state(self) -> EngineState:
        return self._state

    @property
    def episode_status(self) -> EpisodeStatus:
        return self._status

    @property
    def time(self) -> float:
        return self._time

    # -- control -------------------------------------------------------

    def pause(self) -> None:
        if self._state is not EngineState.RUNNING:
            raise RuntimeError(f"cannot pause: engine state is {self._state.value}")
        self._state = EngineState.PAUSED

    def resume(self) -> None:
        if self._state is not EngineState.PAUSED:
            raise RuntimeError(f"cannot resume: engine state is {self._state.value}")
        self._state = EngineState.RUNNING

    def stop(self) -> None:
        """Abort the episode; result status becomes STOPPED."""
        if self._state not in (EngineState.RUNNING, EngineState.PAUSED):
            raise RuntimeError(f"cannot stop: engine state is {self._state.value}")
        self._status = EpisodeStatus.STOPPED
        self._reason = "stopped by user"
        self._events.append(EpisodeEvent(time=self._time, type="stopped", message=self._reason))
        self._state = EngineState.STOPPED

    # -- helpers -------------------------------------------------------

    def _goal_distance(self) -> float:
        assert self._robot is not None and self._scenario is not None
        return euclidean_distance(
            self._robot.pose.position,
            Point2D(x=self._scenario.goal_pose.x, y=self._scenario.goal_pose.y),
        )

    def _trajectory_point(self) -> TrajectoryPoint:
        assert self._robot is not None and self._scenario is not None
        return TrajectoryPoint(
            time=self._time,
            x=self._robot.pose.x,
            y=self._robot.pose.y,
            theta=self._robot.pose.theta,
            linear_velocity=self._robot.linear_velocity,
            angular_velocity=self._robot.angular_velocity,
            obstacles=tuple(
                ObstacleSnapshot(
                    name=obstacle.name,
                    x=circle.center.x,
                    y=circle.center.y,
                    radius=obstacle.radius,
                )
                for obstacle, circle in zip(
                    self._scenario.dynamic_obstacles, self._dynamic_now(), strict=True
                )
            ),
        )

    def _dynamic_now(self) -> tuple[CircleObstacle, ...]:
        """Dynamic obstacles as circles at the current simulation time."""
        assert self._scenario is not None
        return _dynamic_circles(self._scenario, self._time)

    def _sensor_grid_now(self) -> OccupancyGrid:
        """Sensor grid with the current dynamic obstacles burned in.

        Rebuilt per observation: dynamic obstacles move, so the scan must
        see where they are now, not where they started.
        """
        assert self._sensor_grid is not None and self._scenario is not None
        dynamic = self._dynamic_now()
        if not dynamic:
            return self._sensor_grid
        return OccupancyGrid(
            rasterize_obstacles(self._sensor_grid.map_data, dynamic),
            self._sensor_grid.unknown_as_occupied,
        )


def _dynamic_circles(scenario: Scenario, time: float) -> tuple[CircleObstacle, ...]:
    """Positions of every dynamic obstacle at ``time``, as circles."""
    return tuple(
        CircleObstacle(
            center=position_at(obstacle, time, scenario.random_seed), radius=obstacle.radius
        )
        for obstacle in scenario.dynamic_obstacles
    )
