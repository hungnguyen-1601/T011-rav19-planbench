"""The parts of DWA that more than one controller needs.

``dwa`` and ``dwa_predictive`` differ in one idea — whether the world is
rolled forward alongside the robot — and agree about everything else: how
the reachable velocity window is built, how a candidate is forward
simulated, how a LiDAR scan becomes points, how far a point is from the
global path. That agreement lives here.

**Functions, not a base class, and the reason is the candidate id.**
``StackComponent.version`` is part of what identifies a candidate, and the
platform's promise is that "the same DWA after a bug fix is a different
candidate". A shared parent class quietly breaks that promise in the one
direction nobody checks: a fix applied to the parent changes *both*
controllers, and the artifact records two ids that did not move. Two
classes calling the same pure functions have the same code-sharing
benefit and leave the checksum honest — see the ``local_version`` work in
P6, which hashes this module alongside the controller's own.

**What deliberately stayed behind.** The admissible-speed bound is not
here. It is the hard constraint of contract L2, it belongs to
``planbench_schemas.feasibility.admissible_speed``, and the controller
reaches it through its own ``_speed_that_stops_within`` because the
reaction time is the controller's control period. Keeping the soft
machinery here and the hard bound there is the same split the rest of the
codebase already makes; putting them in one module would invite a future
reader to hand this one a candidate configuration.

Every function is pure and takes primitives rather than a config object.
That is not style: a shared helper that accepted ``DWAConfig`` would be a
helper ``dwa_predictive`` could only use by inheriting the other
controller's schema.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from planbench_schemas.episode import Observation
from planbench_schemas.geometry import EPS, Point2D
from planbench_schemas.robot import RobotConfig, RobotState

__all__ = [
    "distance_to_polyline",
    "final_heading",
    "linspace",
    "obstacle_points",
    "reachable_window",
    "rollout_batch",
    "sample_window",
]


def linspace(low: float, high: float, count: int) -> list[float]:
    """``count`` evenly spaced values, or a single value on a degenerate range.

    The collapse to ``[low]`` is not a guard against division by zero —
    it is what "the window has no width" means. A robot pinned to one
    speed has one speed to consider, and returning ``count`` copies of it
    would multiply the scoring work by nothing.
    """
    if high - low <= EPS:
        return [low]
    step = (high - low) / (count - 1)
    return [low + step * i for i in range(count)]


def reachable_window(
    state: RobotState,
    robot: RobotConfig,
    control_period: float,
    allow_reverse: bool,
) -> tuple[float, float, float, float]:
    """``(v_min, v_max, w_min, w_max)`` the actuators can reach in one period.

    This is the *dynamic window* proper, and only that: what the motors
    can do next, bounded by the robot's velocity and acceleration limits.

    **It is not the whole speed limit and must not become it.** Whether
    the robot may then *hold* that speed — whether it could still stop
    before what it can see — is the admissible-velocity criterion, which
    is deployment-owned and lives in
    :func:`~planbench_schemas.feasibility.admissible_speed`. The caller
    applies it afterwards. Folding it in here would put the hard
    constraint of contract L2 inside a function whose other arguments are
    candidate-owned, which is the arrangement the layering exists to
    prevent.
    """
    dv = robot.max_linear_acceleration * control_period
    dw = robot.max_angular_acceleration * control_period
    v_min = max(
        -robot.max_linear_velocity if allow_reverse else 0.0,
        state.linear_velocity - dv,
    )
    v_max = min(robot.max_linear_velocity, state.linear_velocity + dv)
    w_min = max(-robot.max_angular_velocity, state.angular_velocity - dw)
    w_max = min(robot.max_angular_velocity, state.angular_velocity + dw)
    return v_min, v_max, w_min, w_max


def sample_window(
    v_min: float,
    v_max: float,
    w_min: float,
    w_max: float,
    velocity_samples: int,
    omega_samples: int,
) -> list[tuple[float, float]]:
    """The window on a fixed grid, in a fixed order.

    Determinism is a contract, not a convenience: ties are broken by
    first-lowest-cost in this order, so the order *is* part of what a
    candidate does. Two runs of one candidate that sampled the same set
    in a different sequence would pick different commands on ties and
    look like two candidates.
    """
    velocities = linspace(v_min, v_max, velocity_samples)
    omegas = linspace(w_min, w_max, omega_samples)
    return [(v, w) for v in velocities for w in omegas]


def rollout_batch(
    state: RobotState,
    candidates: Sequence[tuple[float, float]],
    obstacles: np.ndarray,
    horizon_seconds: float,
    horizon_dt: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Forward-simulate every candidate at once (vectorized).

    Returns ``(points, clearances)`` with shapes ``(N, K, 2)`` and
    ``(N,)``. Integration matches the simulator exactly: the position step
    uses the heading *before* that step's rotation. "Matches the
    simulator" is load-bearing — a controller that predicted its own
    motion under a different integrator would reject trajectories it can
    drive and accept ones it cannot, and the error would grow with the
    horizon rather than announcing itself.

    ``clearances`` is the minimum over both the horizon and the obstacle
    set: the nearest the whole trajectory ever comes to anything. Infinite
    when nothing is in range, which is the correct answer in an empty room
    rather than a sentinel.

    The obstacle set carries **no time axis** here, which is exactly the
    difference ``dwa_predictive`` exists to remove: the broadcast below
    compares a trajectory that spans the horizon against a world frozen at
    the moment of the scan.
    """
    steps = max(1, int(round(horizon_seconds / horizon_dt)))
    dt = horizon_dt

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


def obstacle_points(observation: Observation) -> np.ndarray:
    """Convert the LiDAR scan into world-frame points (skip max-range rays).

    Returns an ``(M, 2)`` array; empty when nothing is in range.

    Built from ``observation.pose`` — where the robot *believes* it is —
    because that is all a controller has. The ray angles mirror
    ``planbench_simulator.lidar.scan``; two definitions of the same sweep
    is how they come to disagree.

    A ray returning its maximum range means *nothing was hit*, not
    *something is at maximum range*, so those rays contribute no point. A
    costmap that read them as returns would place a wall in open space at
    exactly the radius the sensor stops seeing.
    """
    ranges = observation.lidar_ranges
    if not ranges:
        return np.empty((0, 2))
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


def final_heading(trajectory: Sequence[Point2D]) -> float:
    """Bearing of the last segment of a rolled-out trajectory."""
    if len(trajectory) < 2:
        return 0.0
    a, b = trajectory[-2], trajectory[-1]
    if math.hypot(b.x - a.x, b.y - a.y) <= EPS:
        return math.atan2(b.y - a.y, b.x - a.x) if (b.x - a.x or b.y - a.y) else 0.0
    return math.atan2(b.y - a.y, b.x - a.x)


def distance_to_polyline(point: Point2D, polyline: Sequence[Point2D]) -> float:
    """Shortest distance from a point to a polyline (segment-wise).

    Segment-wise rather than vertex-wise, and the difference is the whole
    point: a global path may put its waypoints metres apart, and a robot
    sitting beside the middle of a long straight is *on* the path even
    though it is nowhere near either end of it.
    """
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
