"""Deterministic single-episode simulation engine.

Lifecycle: ``load_map()`` → ``load_scenario()`` → ``reset()`` → repeated
``step(action)`` until ``is_done()``, then ``get_result()``.
``pause()/resume()/stop()`` control execution between steps.

Termination checks run after every step in a fixed priority order
(first match wins): collision > goal reached > timeout > stuck >
failure to progress.

A stuck or no-progress termination is not necessarily final: a stack
with replanning enabled can hand the robot a new global path and call
``resume_after_replan()``. Collision and timeout never reopen.

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
from planbench_schemas.geometry import EPS, Point2D, Pose2D, euclidean_distance, normalize_angle
from planbench_schemas.map import MapData
from planbench_schemas.robot import RobotState, SimAction
from planbench_schemas.scenario import CircleObstacle, Scenario
from planbench_simulator.collision import collides_with_grid, collides_with_obstacle
from planbench_simulator.grid import OccupancyGrid, rasterize_obstacles
from planbench_simulator.kinematics import step as kinematics_step
from planbench_simulator.lidar import scan
from planbench_simulator.noise import NoiseModel


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
        self._noise: NoiseModel | None = None
        self._state = EngineState.IDLE
        self._status = EpisodeStatus.RUNNING
        self._reason = ""
        self._robot: RobotState | None = None
        self._time = 0.0
        self._steps = 0
        self._trajectory: list[TrajectoryPoint] = []
        self._events: list[EpisodeEvent] = []
        #: Commands issued but not yet in effect, when the deployment
        #: declares a control latency. Per episode, so a re-run starts
        #: with an empty pipe rather than the tail of the last one.
        self._pending_actions: list[SimAction] = []
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
        # Fixed by the episode's own seed, so the draws are reproducible
        # from the context id alone and never from the clock (HĐ-3.2).
        self._noise = NoiseModel(spec=scenario.sensor_noise, seed=scenario.random_seed)
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
        self._pending_actions = []
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

        # Wheel slip perturbs the command *before* the kinematics, so the
        # acceleration and velocity limits still bound what the robot can
        # physically do — a slipping wheel does not lend the robot a
        # larger envelope. The resulting pose is the true one, and the
        # collision test below judges on it, because the robot really did
        # end up there.
        self._robot = kinematics_step(
            self._robot, self._slipped(self._delayed(action)), scenario.robot, dt
        )
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
        # Where the robot *believes* it is. Until 2026-08-13 this was the
        # true pose, so every candidate navigated with perfect
        # localisation — a whole family of real failures (drift, a bad
        # fix that stays bad, driving confidently into a wall) simply did
        # not exist here.
        #
        # The scan is taken from the **true** pose and the ranges are then
        # reported against the believed one, which is what a real robot
        # has: the beams really did bounce off the walls that are there,
        # and only the robot's idea of where it was standing is wrong.
        believed = self._believed_pose()
        goal = self._scenario.goal_pose
        bearing = normalize_angle(
            math.atan2(goal.y - believed.y, goal.x - believed.x) - believed.theta
        )
        return Observation(
            time=self._time,
            pose=believed,
            linear_velocity=self._robot.linear_velocity,
            angular_velocity=self._robot.angular_velocity,
            # Distance to the goal as the robot can work it out: from
            # where it thinks it is. Reporting the true distance beside a
            # believed pose would hand back a cross-check no robot has,
            # and a controller could recover the true pose from it.
            goal_distance=math.hypot(goal.x - believed.x, goal.y - believed.y),
            goal_bearing=bearing,
            lidar_ranges=self._measured_ranges(self._robot.pose),
        )

    def _believed_pose(self) -> Pose2D:
        """The true pose plus this step's localisation error.

        Measurement error, so it must never reach the collision test —
        the same rule LiDAR range noise follows. A collision judged on a
        believed pose would simulate a different world instead of a robot
        that does not know where it is, and it would let a badly
        localised robot pass through walls it truly hit.
        """
        assert self._robot is not None
        if self._noise is None or not self._noise.active:
            return self._robot.pose
        dx, dy, dtheta = self._noise.pose_error(self._steps)
        if dx == 0.0 and dy == 0.0 and dtheta == 0.0:
            return self._robot.pose
        pose = self._robot.pose
        return Pose2D(
            x=pose.x + dx,
            y=pose.y + dy,
            theta=normalize_angle(pose.theta + dtheta),
        )

    def is_done(self) -> bool:
        return self._state in (EngineState.FINISHED, EngineState.STOPPED)

    def dynamic_obstacles_now(self) -> tuple[CircleObstacle, ...]:
        """Ground-truth positions of the dynamic obstacles at this instant.

        Public because replanning needs it: a global planner handed only
        the static map replans the exact route it just planned, since
        nothing in its input changed. The stack burns these circles into
        a throwaway planning grid so the new route goes around whatever
        is blocking the robot *now*.

        This is ground truth, and it is only ever read by the stack
        between control steps, never by a planner through
        :meth:`get_observation` — the information-parity declaration
        (P02) still holds, because what a controller sees is unchanged.
        """
        if self._scenario is None:
            raise RuntimeError("load_scenario() must be called before dynamic_obstacles_now()")
        return self._dynamic_now()

    def resume_after_replan(self, note: str, event_type: str = "replan") -> None:
        """Revive an episode that ended STUCK or NO_PROGRESS.

        Only those two statuses: a collision or a timeout is a verdict on
        the episode, and letting a new path undo it would let replanning
        buy results it did not earn.

        Two things have to be undone, not one. Flipping the state back to
        RUNNING is the obvious half; the other is the sliding window that
        detected the standstill. Its samples all still describe a robot
        that has not moved, so without reseeding it the very next step
        re-derives the same verdict and the replan achieves nothing.
        Seeding it with a single sample at the current time restarts both
        the stuck and the no-progress clocks from here.

        The terminating event is replaced by an event of ``event_type``
        carrying ``note``. Leaving the ``stuck`` event in place would put
        a termination in the record of an episode that did not terminate
        there; the replacement keeps the same moment, and the reason,
        visible.

        ``event_type`` exists because a replan is not the only thing that
        can revive a standstill — a recovery behaviour backs the robot
        away from what it was stuck against and the episode carries on.
        The two must stay **distinguishable in the record**: "the planner
        found another way" and "the robot backed up and tried again" are
        different facts about a stack, and collapsing them under one
        event name would make a run that recovered five times read like
        one that replanned five times.
        """
        if self._state is not EngineState.FINISHED or self._status not in (
            EpisodeStatus.STUCK,
            EpisodeStatus.NO_PROGRESS,
        ):
            raise RuntimeError(
                f"cannot resume ({event_type}): engine state is {self._state.value} "
                f"with status {self._status.value}"
            )
        assert self._robot is not None
        if self._events and self._events[-1].type == self._status.value:
            self._events.pop()
        self._events.append(EpisodeEvent(time=self._time, type=event_type, message=note))
        self._status = EpisodeStatus.RUNNING
        self._reason = ""
        self._window = deque(
            [(self._time, self._robot.pose.x, self._robot.pose.y, self._goal_distance())]
        )
        self._state = EngineState.RUNNING

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

    @property
    def steps(self) -> int:
        """Simulation steps taken since ``reset()``.

        Public because the provider seam addresses randomness by tick
        (see ``host.runtime_view``), and a seam that had to reach for
        ``_steps`` would be documenting one boundary while crossing
        another. It is the same counter the noise model already indexes
        its streams by, so two providers reading one tick and the engine
        drawing that tick's noise agree by construction.
        """
        return self._steps

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

    def _delayed(self, action: SimAction) -> SimAction:
        """The command that actually takes effect this step.

        A real ``/cmd_vel`` arrives late: the controller decides, the
        message travels, the driver applies it. A stack tuned against an
        instant response is measured more kindly than it deserves, and
        the gap widens exactly where it hurts — close to an obstacle,
        where the command that matters is the one issued a moment ago.

        Held in a queue rather than by re-reading history, because the
        commands are the caller's and the engine has no record of what it
        was told before. Until the queue fills, the robot holds still:
        that is what a drive does before the first command reaches it,
        and inventing a zero-latency first command would give away
        exactly the head start being modelled.
        """
        if self._noise is None:
            return action
        depth = self._noise.spec.command_latency_steps
        if depth <= 0:
            return action
        self._pending_actions.append(action)
        if len(self._pending_actions) <= depth:
            return SimAction(linear_velocity=0.0, angular_velocity=0.0)
        return self._pending_actions.pop(0)

    def _slipped(self, action: SimAction) -> SimAction:
        """The command as the wheels actually deliver it.

        Actuation error, not measurement error: this one is allowed to
        change the world, because the robot really did move differently
        from what it was told. Indexed by step number rather than drawn
        from a running stream, so two candidates sharing an episode
        context meet the same slip sequence however differently they
        drive (see :mod:`planbench_simulator.noise`).
        """
        assert self._noise is not None
        if not self._noise.active:
            return action
        linear, angular = self._noise.slip_factors(self._steps)
        # Systematic bias multiplies on top of the zero-mean slip rather
        # than replacing it, because they are two different faults and a
        # real drive has both: a wet patch this step, and a wheel that has
        # been worn small since last month. Slip averages out over an
        # episode; the bias does not, which is the point of having it.
        bias_linear, bias_angular = self._noise.odometry_bias()
        return SimAction(
            linear_velocity=action.linear_velocity * linear * bias_linear,
            angular_velocity=action.angular_velocity * angular * bias_angular,
        )

    def _measured_ranges(self, pose: Pose2D) -> tuple[float, ...]:
        """LiDAR as the robot reads it, errors and all.

        Measurement error only. The geometry is untouched and the
        collision test never sees this — a noisy range that makes the
        robot *think* a wall is 2 cm further away must not move the wall.

        Clamped to a non-negative distance no greater than ``max_range``:
        a range finder reports what it can report, and a negative
        distance is not a reading any consumer should have to defend
        against.
        """
        assert self._scenario is not None and self._noise is not None
        ranges = scan(self._sensor_grid_now(), pose, self._scenario.lidar)
        ceiling = self._scenario.lidar.max_range
        offsets = self._noise.lidar_offsets(self._steps, len(ranges))
        if offsets is not None:
            ranges = tuple(
                min(ceiling, max(0.0, value + float(offset)))
                for value, offset in zip(ranges, offsets, strict=True)
            )
        # Dropout last, so a ray that returned nothing reports nothing
        # rather than nothing-plus-a-range-error. A dropped return is
        # **maximum range**, never zero: zero reads as an obstacle
        # touching the sensor, which is the opposite of what happened and
        # would make dropout the safest event a planner can meet instead
        # of the one that drives robots into glass.
        dropped = self._noise.dropout_mask(self._steps, len(ranges))
        if dropped is not None:
            ranges = tuple(
                ceiling if is_dropped else value
                for value, is_dropped in zip(ranges, dropped, strict=True)
            )
        return ranges

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
