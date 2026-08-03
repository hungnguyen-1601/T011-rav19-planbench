"""Dynamic Window Approach (DWA) local planner.

Algorithm per step:

1. Build the dynamic window: velocities reachable within one control
   period given the robot's velocity and acceleration limits.
2. Sample the window on a fixed grid (``velocity_samples`` ×
   ``omega_samples``) — deterministic, no randomness.
3. Forward-simulate each candidate for ``horizon_seconds`` using the
   *same* explicit-Euler kinematics as the simulator, holding (v, w).
4. Reject candidates whose predicted trajectory collides (obstacle
   distance from the LiDAR-derived point cloud ``<= robot radius``).
5. Score the survivors with a weighted cost and pick the minimum.

Cost components (all normalized to roughly [0, 1] before weighting, so
weights are comparable):

- ``goal``: distance from the trajectory end to the local goal, divided
  by ``lookahead_distance``. Without this term nothing rewards *arriving*:
  once the robot is aligned and on the path, ``heading`` and ``path`` are
  both zero, so clearance alone decides and the robot parks short of a
  goal that sits near a wall.
- ``heading``: |bearing to the local goal| / pi at the trajectory end.
- ``path``: distance from the trajectory end to the global path,
  divided by ``path_distance_scale``.
- ``clearance``: 1 - min(clearance, clearance_cap) / clearance_cap
  along the trajectory (larger clearance is cheaper).
- ``velocity``: 1 - v / max_linear_velocity (prefers moving forward).
- ``smoothness``: |v - v_prev| / max_linear_velocity +
  |w - w_prev| / max_angular_velocity. Normalizing by the robot limits
  (not by the per-period acceleration window) keeps this term on the
  same scale as ``velocity``; normalizing by the window made a full
  acceleration cost more than the speed it bought, so the robot never
  accelerated.
- ``oscillation``: 1 when w flips sign versus the previous command
  while |w| is meaningful, else 0.

Obstacles come from the LiDAR scan in the observation, not from the
ground-truth map: the local planner only sees what the robot senses.

Deterministic: fixed sample ordering, ties broken by first-lowest-cost
in that order; no global state beyond the previous command.
"""

from __future__ import annotations

import math
import time
from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import Observation
from planbench_schemas.geometry import EPS, Point2D, normalize_angle
from planbench_schemas.robot import RobotConfig, RobotState, SimAction


class DWAConfig(BaseModel):
    """Tunables for :class:`DWAPlanner` (no magic numbers in the code)."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    control_period: float = Field(default=0.1, gt=0, description="Control period, seconds.")
    horizon_seconds: float = Field(default=1.5, gt=0, description="Forward-simulation horizon.")
    horizon_dt: float = Field(default=0.1, gt=0, description="Forward-simulation step.")
    velocity_samples: int = Field(default=9, ge=2)
    omega_samples: int = Field(default=15, ge=2)
    lookahead_distance: float = Field(default=1.2, gt=0, description="Local goal lookahead, m.")
    allow_reverse: bool = False

    weight_goal: float = Field(default=2.0, ge=0)
    weight_heading: float = Field(default=1.0, ge=0)
    weight_path: float = Field(default=1.4, ge=0)
    weight_clearance: float = Field(default=1.2, ge=0)
    weight_velocity: float = Field(default=0.6, ge=0)
    weight_smoothness: float = Field(default=0.15, ge=0)
    weight_oscillation: float = Field(default=0.25, ge=0)

    clearance_cap: float = Field(
        default=0.6,
        gt=0,
        description=(
            "Clearance treated as fully safe, metres. Roughly two robot radii: "
            "beyond it the clearance cost is zero, so open space carries no "
            "penalty and tight-but-safe passages stay affordable."
        ),
    )
    path_distance_scale: float = Field(default=1.5, gt=0)
    oscillation_omega_threshold: float = Field(default=0.2, ge=0)
    safety_margin: float = Field(
        default=0.05, ge=0, description="Extra metres required beyond the robot radius."
    )


class DWAPlanner(LocalPlanner):
    """Deterministic DWA controller over LiDAR-sensed obstacles."""

    def __init__(self, config: DWAConfig | None = None) -> None:
        self._config = config or DWAConfig()
        self._robot: RobotConfig | None = None
        self._path: tuple[Point2D, ...] = ()
        self._path_index = 0
        self._previous: SimAction | None = None

    @property
    def name(self) -> str:
        return "dwa"

    @property
    def control_period(self) -> float:
        return self._config.control_period

    @property
    def config(self) -> DWAConfig:
        return self._config

    def reset(self, global_path: Sequence[Point2D], robot: RobotConfig) -> None:
        if not global_path:
            raise ValueError("DWA requires a non-empty global path")
        self._path = tuple(global_path)
        self._robot = robot
        self._path_index = 0
        self._previous = None

    def compute(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        if self._robot is None:
            raise RuntimeError("reset() must be called before compute()")
        started_at = time.perf_counter()
        config = self._config
        robot = self._robot

        local_goal = self._advance_local_goal(state)
        obstacles = self._obstacle_points(observation)
        candidates = self._dynamic_window(state)
        rollouts, clearances = self._rollout_batch(state, candidates, obstacles)

        keep_out = robot.radius + config.safety_margin
        best_cost = math.inf
        best: tuple[SimAction, tuple[Point2D, ...], dict[str, float]] | None = None
        blocked = 0
        for index, (velocity, omega) in enumerate(candidates):
            if clearances[index] <= keep_out:
                blocked += 1
                continue
            trajectory = tuple(Point2D(x=float(px), y=float(py)) for px, py in rollouts[index])
            components = self._score(
                velocity, omega, trajectory, float(clearances[index]), local_goal
            )
            total = sum(components.values())
            if total < best_cost - EPS:
                best_cost = total
                best = (
                    SimAction(linear_velocity=velocity, angular_velocity=omega),
                    trajectory,
                    components,
                )

        latency = time.perf_counter() - started_at
        if best is None:
            # Safety fallback: full stop, decelerating within the limits.
            action = SimAction(linear_velocity=0.0, angular_velocity=0.0)
            self._previous = action
            return LocalPlanResult(
                action=action,
                latency_seconds=latency,
                failure_reason=(
                    f"all {len(candidates)} candidate velocities collide "
                    f"({blocked} rejected); commanding stop"
                ),
            )

        action, trajectory, components = best
        self._previous = action
        return LocalPlanResult(
            action=action,
            predicted_trajectory=trajectory,
            cost_components=components,
            latency_seconds=latency,
        )

    # -- internals -----------------------------------------------------

    def _dynamic_window(self, state: RobotState) -> list[tuple[float, float]]:
        """Reachable (v, w) pairs on a deterministic sample grid."""
        assert self._robot is not None
        robot, config = self._robot, self._config
        dv = robot.max_linear_acceleration * config.control_period
        dw = robot.max_angular_acceleration * config.control_period
        v_min = max(
            -robot.max_linear_velocity if config.allow_reverse else 0.0,
            state.linear_velocity - dv,
        )
        v_max = min(robot.max_linear_velocity, state.linear_velocity + dv)
        w_min = max(-robot.max_angular_velocity, state.angular_velocity - dw)
        w_max = min(robot.max_angular_velocity, state.angular_velocity + dw)

        # Admissible-velocity criterion: never travel faster than the
        # robot can brake before the end of the path. Without this the
        # controller charges the goal at full speed and orbits it,
        # because nothing else rewards arriving.
        remaining = math.hypot(self._path[-1].x - state.pose.x, self._path[-1].y - state.pose.y)
        stopping_limit = math.sqrt(2.0 * robot.max_linear_acceleration * max(remaining, 0.0))
        v_max = min(v_max, stopping_limit)
        v_min = min(v_min, v_max)

        velocities = _linspace(v_min, v_max, config.velocity_samples)
        omegas = _linspace(w_min, w_max, config.omega_samples)
        return [(v, w) for v in velocities for w in omegas]

    def _rollout_batch(
        self,
        state: RobotState,
        candidates: Sequence[tuple[float, float]],
        obstacles: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Forward-simulate every candidate at once (vectorized).

        Returns ``(points, clearances)`` with shapes ``(N, K, 2)`` and
        ``(N,)``. Integration matches the simulator exactly: the position
        step uses the heading *before* that step's rotation.
        """
        config = self._config
        steps = max(1, int(round(config.horizon_seconds / config.horizon_dt)))
        dt = config.horizon_dt

        velocities = np.array([candidate[0] for candidate in candidates], dtype=float)
        omegas = np.array([candidate[1] for candidate in candidates], dtype=float)
        # Heading before step k (k = 0 .. steps-1).
        step_index = np.arange(steps, dtype=float)
        headings = state.pose.theta + np.outer(omegas, step_index) * dt  # (N, K)
        deltas_x = (velocities[:, None] * np.cos(headings)) * dt
        deltas_y = (velocities[:, None] * np.sin(headings)) * dt
        points = np.stack(
            (
                state.pose.x + np.cumsum(deltas_x, axis=1),
                state.pose.y + np.cumsum(deltas_y, axis=1),
            ),
            axis=2,
        )  # (N, K, 2)

        if obstacles.size == 0:
            return points, np.full(len(candidates), math.inf)
        # (N, K, M) distances -> min over horizon steps and obstacles.
        diff = points[:, :, None, :] - obstacles[None, None, :, :]
        clearances = np.sqrt(np.einsum("nkmd,nkmd->nkm", diff, diff)).min(axis=(1, 2))
        return points, clearances

    def _score(
        self,
        velocity: float,
        omega: float,
        trajectory: Sequence[Point2D],
        clearance: float,
        local_goal: Point2D,
    ) -> dict[str, float]:
        assert self._robot is not None
        robot, config = self._robot, self._config
        end = trajectory[-1]

        # Heading: bearing from the trajectory end to the local goal.
        approach = math.atan2(local_goal.y - end.y, local_goal.x - end.x)
        end_theta = _final_heading(trajectory)
        heading = abs(normalize_angle(approach - end_theta)) / math.pi
        goal_distance = (
            math.hypot(local_goal.x - end.x, local_goal.y - end.y) / config.lookahead_distance
        )

        path_distance = _distance_to_polyline(end, self._path) / config.path_distance_scale
        usable = min(max(clearance - robot.radius, 0.0), config.clearance_cap)
        clearance_cost = 1.0 - usable / config.clearance_cap
        velocity_cost = 1.0 - abs(velocity) / robot.max_linear_velocity

        if self._previous is None:
            smoothness = 0.0
            oscillation = 0.0
        else:
            smoothness = (
                abs(velocity - self._previous.linear_velocity) / robot.max_linear_velocity
                + abs(omega - self._previous.angular_velocity) / robot.max_angular_velocity
            )
            flips = omega * self._previous.angular_velocity < 0
            significant = (
                abs(omega) > config.oscillation_omega_threshold
                and abs(self._previous.angular_velocity) > config.oscillation_omega_threshold
            )
            oscillation = 1.0 if (flips and significant) else 0.0

        return {
            "goal": config.weight_goal * min(goal_distance, 5.0),
            "heading": config.weight_heading * heading,
            "path": config.weight_path * min(path_distance, 5.0),
            "clearance": config.weight_clearance * clearance_cost,
            "velocity": config.weight_velocity * velocity_cost,
            "smoothness": config.weight_smoothness * min(smoothness, 5.0),
            "oscillation": config.weight_oscillation * oscillation,
        }

    def _advance_local_goal(self, state: RobotState) -> Point2D:
        """Lookahead point on the global path; the index never moves back."""
        position = state.pose.position
        last = len(self._path) - 1
        while self._path_index < last:
            distance = math.hypot(
                self._path[self._path_index].x - position.x,
                self._path[self._path_index].y - position.y,
            )
            if distance >= self._config.lookahead_distance:
                break
            self._path_index += 1
        return self._path[self._path_index]

    def _obstacle_points(self, observation: Observation) -> np.ndarray:
        """Convert the LiDAR scan into world-frame points (skip max-range rays).

        Returns an ``(M, 2)`` array; empty when nothing is in range.
        """
        ranges = observation.lidar_ranges
        if not ranges:
            return np.empty((0, 2))
        # Ray i angle mirrors planbench_simulator.lidar.scan.
        span = 2.0 * math.pi
        increment = span / len(ranges)
        start = observation.pose.theta - span / 2.0
        max_range = max(ranges)
        points: list[tuple[float, float]] = []
        for index, distance in enumerate(ranges):
            if distance >= max_range - EPS:
                continue  # no return along this ray
            angle = start + index * increment
            points.append(
                (
                    observation.pose.x + distance * math.cos(angle),
                    observation.pose.y + distance * math.sin(angle),
                )
            )
        return np.array(points, dtype=float) if points else np.empty((0, 2))


def _linspace(low: float, high: float, count: int) -> list[float]:
    if high - low <= EPS:
        return [low]
    step = (high - low) / (count - 1)
    return [low + step * i for i in range(count)]


def _final_heading(trajectory: Sequence[Point2D]) -> float:
    if len(trajectory) < 2:
        return 0.0
    a, b = trajectory[-2], trajectory[-1]
    if math.hypot(b.x - a.x, b.y - a.y) <= EPS:
        return math.atan2(b.y - a.y, b.x - a.x) if (b.x - a.x or b.y - a.y) else 0.0
    return math.atan2(b.y - a.y, b.x - a.x)


def _distance_to_polyline(point: Point2D, polyline: Sequence[Point2D]) -> float:
    """Shortest distance from a point to a polyline (segment-wise)."""
    if not polyline:
        return 0.0
    if len(polyline) == 1:
        return math.hypot(point.x - polyline[0].x, point.y - polyline[0].y)
    best = math.inf
    for a, b in zip(polyline, polyline[1:], strict=False):
        dx, dy = b.x - a.x, b.y - a.y
        length_squared = dx * dx + dy * dy
        if length_squared <= EPS:
            distance = math.hypot(point.x - a.x, point.y - a.y)
        else:
            t = max(0.0, min(1.0, ((point.x - a.x) * dx + (point.y - a.y) * dy) / length_squared))
            distance = math.hypot(point.x - (a.x + t * dx), point.y - (a.y + t * dy))
        best = min(best, distance)
    return best
