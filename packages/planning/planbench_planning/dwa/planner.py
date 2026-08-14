"""Dynamic Window Approach (DWA) local planner.

Algorithm per step:

1. Build the dynamic window: velocities reachable within one control
   period given the robot's velocity and acceleration limits, further
   bounded by the speed the robot could still stop from before the
   nearest obstacle. The window and that bound are **different
   constraints** — the first is about the actuators, the second about
   the world — and the name "Dynamic Window" covers only the first.
2. Sample the window on a fixed grid (``velocity_samples`` ×
   ``omega_samples``) — deterministic, no randomness.
3. Forward-simulate each candidate for ``horizon_seconds`` using the
   *same* explicit-Euler kinematics as the simulator, holding (v, w).
4. Reject candidates whose predicted trajectory enters the hard feasible
   set's boundary — obstacle distance from the LiDAR-derived point cloud
   below ``hard_clearance(robot, envelope)``. That threshold is
   deployment-owned; no candidate parameter may narrow it (contract L2).
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
- ``comfort``: how far inside ``safety_margin`` of the hard boundary the
  trajectory reaches, squared. This is where ``safety_margin`` lives now
  that it no longer rejects anything: wanting more room than safety
  requires is a legitimate preference and still separates two
  candidates, but a preference may not shrink the set the global planner
  planned against.
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
from planbench_schemas.feasibility import SafetyEnvelope, admissible_speed, hard_clearance
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
        default=0.05,
        ge=0,
        description=(
            "Metres of room beyond the hard boundary this candidate would like. "
            "A preference, priced by the `comfort` cost — not a refusal. It used "
            "to be the hard threshold, which let a candidate silently narrow the "
            "feasible set the global planner had planned against."
        ),
    )


class DWAPlanner(LocalPlanner):
    """Deterministic DWA controller over LiDAR-sensed obstacles."""

    def __init__(self, config: DWAConfig | None = None) -> None:
        self._config = config or DWAConfig()
        self._robot: RobotConfig | None = None
        self._envelope = SafetyEnvelope()
        self._obstacle_speed = 0.0
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

    def reset(
        self,
        global_path: Sequence[Point2D],
        robot: RobotConfig,
        envelope: SafetyEnvelope | None = None,
        obstacle_speed: float | None = None,
    ) -> None:
        """Adopt a path, and be told the hard feasible set to respect.

        ``envelope`` is **deployment-owned** and arrives as its own
        argument for a reason that is the whole point of the layering:
        the hard feasible set must not be reachable from this
        controller's configuration. A candidate that wanted to narrow it
        has no field to do it with (contract L2).

        Optional only so a caller that declares no sensing noise — the
        shipped profiles, every unit test written before this existed —
        gets the footprint alone, which is the correct envelope for a
        robot whose pose estimate is exact.

        ``obstacle_speed`` is the deployment's ``v_obstacle_max``, and it
        arrives the same way and for the same reason. ``None`` means the
        deployment declares no bound, which is treated as zero: the
        behaviour measured before the field existed, and a deployment
        that says nothing gets no guarantee rather than a guessed one.
        """
        if not global_path:
            raise ValueError("DWA requires a non-empty global path")
        self._path = tuple(global_path)
        self._robot = robot
        self._envelope = envelope or SafetyEnvelope()
        self._obstacle_speed = obstacle_speed or 0.0
        self._path_index = 0
        self._previous = None

    def compute(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        if self._robot is None:
            raise RuntimeError("reset() must be called before compute()")
        started_at = time.perf_counter()
        robot = self._robot

        local_goal = self._advance_local_goal(state)
        obstacles = self._obstacle_points(observation)
        candidates = self._dynamic_window(state, obstacles)
        rollouts, clearances = self._rollout_batch(state, candidates, obstacles)

        # **The hard feasible set, not a preference.** This used to be
        # `robot.radius + config.safety_margin` — a candidate parameter
        # acting as a hard refusal, which let a stack silently narrow the
        # set the global planner had planned against (contract L2). It is
        # now the shared clearance: footprint plus the deployment's
        # safety envelope, both deployment-owned.
        #
        # `safety_margin` survives as a *soft* term in `_score`. Wanting
        # five more centimetres is a legitimate thing for a candidate to
        # want, and it still distinguishes two candidates — by cost,
        # rather than by moving a boundary the planner cannot see.
        keep_out = hard_clearance(robot, self._envelope)
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

    def _dynamic_window(
        self, state: RobotState, obstacles: np.ndarray
    ) -> list[tuple[float, float]]:
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

        # **Admissible-velocity criterion, against the nearer of two
        # things.** The classic form (Fox, Burgard and Thrun 1997) bounds
        # speed by what the robot can brake before the *obstacle* on that
        # curvature; this used to bound it only by the distance to the
        # end of the path, which made it a goal-arrival device wearing a
        # safety name. The two coincide only when the goal is the nearest
        # thing, and on `sudden_stop` the goal is 12.5 m away while the
        # cart is at 7.0 m.
        #
        # What that cost, measured: with `weight_clearance` turned down
        # and a short horizon — both ordinary candidate settings — the
        # robot ran 23 consecutive steps at a speed it could not stop
        # from and hit the cart. Safety was resting on a soft weight the
        # candidate owns, which is the same defect as a hard keep-out
        # owned by the candidate, in the opposite direction.
        #
        # The dynamic window alone does not cover this. It bounds
        # `(v, ω)` by the acceleration reachable in one step; it never
        # asks "once I am there, can I still stop". Nor does the rollout:
        # a trajectory can clear everything inside a one-second horizon
        # and be travelling too fast to stop before what lies just past
        # it.
        #
        # **And the scan is a photograph.** Measuring the headroom
        # against the returns available now says "the robot can stop
        # before the obstacle that is *standing*", which is a different
        # promise from the one a moving site needs. P0 measured the
        # difference: a cart closing at 0.2 m/s took the robot through
        # step after step this criterion called admissible, and it hit.
        # `obstacle_speed` is the deployment's declared worst case, so
        # the bound now covers the ground the obstacle takes as well —
        # equally for every candidate, since the number is not one of
        # theirs to choose.
        to_goal = math.hypot(self._path[-1].x - state.pose.x, self._path[-1].y - state.pose.y)
        to_obstacle = self._nearest_obstacle_distance(obstacles, state)
        headroom = max(0.0, min(to_goal, to_obstacle))
        stopping_limit = self._speed_that_stops_within(headroom, robot)
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

        # `safety_margin` as a preference: room this candidate wants
        # beyond the shared hard clearance. Quadratic in how far inside
        # the wanted margin the trajectory sits, so it bites hard close
        # in and vanishes outside — a linear term would still be nudging
        # the robot at ten metres.
        wanted = hard_clearance(robot, self._envelope) + config.safety_margin
        shortfall = max(0.0, wanted - clearance) / max(config.safety_margin, EPS)
        comfort = min(1.0, shortfall) ** 2
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
            # Weighted with the clearance term because it is the same
            # kind of wish; keeping it separate is what lets a reader see
            # that the hard boundary and the preference are two things.
            "comfort": config.weight_clearance * comfort,
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

    def _nearest_obstacle_distance(self, obstacles: np.ndarray, state: RobotState) -> float:
        """Room between the robot's surface and the closest return.

        Infinite when nothing is in range, so the goal is then the only
        thing bounding the speed — which is what the criterion did all
        along, and remains correct in an empty room.
        """
        assert self._robot is not None
        if obstacles.size == 0:
            return math.inf
        deltas = obstacles - np.array([state.pose.x, state.pose.y])
        nearest = float(np.hypot(deltas[:, 0], deltas[:, 1]).min())
        return max(0.0, nearest - hard_clearance(self._robot, self._envelope))

    def _speed_that_stops_within(self, headroom: float, robot: RobotConfig) -> float:
        """Fastest speed from which the robot still stops inside ``headroom``.

        The arithmetic lives in
        :func:`~planbench_schemas.feasibility.admissible_speed`, beside
        the rest of the hard feasible set, so that the one function
        deciding how fast a robot may go takes deployment-owned
        arguments and nothing else. This is the controller supplying its
        reaction time — one control period — and the deployment's
        declared closing speed.
        """
        return admissible_speed(headroom, robot, self._config.control_period, self._obstacle_speed)

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
