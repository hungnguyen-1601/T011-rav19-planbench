"""DWA that rolls the world forward alongside the robot.

The whole idea is one missing axis. ``DWAPlanner`` forward-simulates its
own trajectory across the horizon and compares it against **a photograph
of the world at t=0**, held still for the entire rollout::

    diff = points[:, :, None, :] - obstacles[None, None, :, :]
    #      (N, K, 2)                (1,  1,  M, 2)   <- no time axis

The consequence runs in both directions, and the second is the one people
miss. Against an obstacle that is **leaving**, the controller is too shy:
somebody who has already walked out of the doorway is still standing in
it as far as the rollout is concerned, so the gap scores narrow and the
robot waits for a space that is already empty. Against an obstacle that
is **arriving**, it is too bold: a cart closing at 1 m/s is scored as
parked, so a trajectory cutting across its face is scored as safe.

This controller gives the obstacles a time axis of their own::

    diff = points[:, :, None, :] - predicted[None, :, :, :]
    #      (N, K, 2)                (1,  K,  M, 2)   <- same K

**What it is not allowed to buy.** Prediction earns speed and smoothness,
never safety. Both hard constraints are the ones ``dwa`` has, unchanged
and measured on the same quantities:

* the **set** refusal — ``clearances <= hard_clearance`` — is computed
  from the points the LiDAR returned **at this instant**, exactly as
  before. Feeding it predicted clearances would let
  ``prediction_horizon_seconds``, a candidate parameter, shrink the hard
  feasible set the global planner planned against, which is precisely
  what contract L2 forbids;
* the **speed** bound — the admissible-stopping limit — is likewise
  untouched, and reads the same declared ``v_obstacle_max``.

So ``dwa_predictive`` may not enter anywhere ``dwa`` is forbidden. It may
only pass *sooner* through somewhere both are allowed. The argument for
that is stronger than the contract: **an estimate used to relax a safety
bound turns estimation error into collisions, while an estimate used in a
cost turns it into a suboptimal route.** This module's velocities are
estimates with three known failure modes (P5), and giving a quantity with
three known failure modes the power to lower a safety threshold is
choosing the wrong direction to be wrong in.

**Not a subclass of** :class:`~planbench_planning.dwa.planner.DWAPlanner`,
deliberately. ``StackComponent.version`` is part of a candidate's
identity, so a shared parent would let one bug fix silently change two
candidates while both recorded ids stayed put. The shared code lives in
:mod:`planbench_planning.common.dwa_core` as pure functions instead.

**Where the tracks come from, and why not from here.** ``compute`` reads
them from an injected provider rather than deriving them. At P3 a test
supplies them; at P4 a ground-truth provider does, which measures what
prediction is worth with zero estimation error; at P5 a LiDAR tracker
does. With **no** provider the controller has no tracks, every predictive
term is exactly zero, and the commands are identical to ``dwa`` — which
is asserted rather than hoped, because "the new terms switch off
cleanly" is the property everything else rests on.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence

import numpy as np
from pydantic import Field

from planbench_planning.common.dwa_core import (
    distance_to_polyline,
    final_heading,
    obstacle_points,
    reachable_window,
    rollout_batch,
    rollout_times,
    sample_window,
)
from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_planning.dwa.planner import DWAConfig
from planbench_planning.dwa_predictive.tracks import ObstacleTrack
from planbench_schemas.episode import Observation
from planbench_schemas.feasibility import SafetyEnvelope, admissible_speed, hard_clearance
from planbench_schemas.geometry import EPS, Point2D, normalize_angle
from planbench_schemas.robot import RobotConfig, RobotState, SimAction

#: What ``compute`` calls to learn about moving obstacles, given the
#: observation's timestamp. Injected, never constructed here: the three
#: implementations that will exist (test double, ground-truth oracle,
#: LiDAR tracker) differ in everything except this signature.
TrackProvider = Callable[[float], Sequence[ObstacleTrack]]


class DWAPredictiveConfig(DWAConfig):
    """``DWAConfig`` plus the two knobs prediction actually needs.

    Inheriting the schema is not the same as inheriting the planner: this
    is a data class, it has no behaviour to be silently shared, and the
    alternative — copying eighteen fields — is how the two controllers
    would come to disagree about what ``clearance_cap`` means.

    **Nothing here can reach the hard feasible set**, which is a property
    worth checking rather than intending: every field below feeds a cost
    term, and a test asserts the refused ``(v, ω)`` set matches ``dwa``'s
    exactly.

    The tracker's own parameters — the association gate, the cluster
    classification thresholds — are **not** here yet. They arrive in P5
    with the tracker that reads them. A configuration field with no
    reader is a knob that appears on ``/candidates`` claiming to change
    something and does not.
    """

    prediction_horizon_seconds: float = Field(
        default=1.5,
        gt=0,
        description=(
            "How far ahead obstacle motion is extrapolated, seconds. Capped by the "
            "rollout horizon in practice — predicting past the end of the trajectory "
            "being scored describes a robot that is not there."
        ),
    )
    weight_time_to_collision: float = Field(
        default=1.0,
        ge=0,
        description=(
            "Price on how soon a trajectory would meet a moving obstacle if both "
            "held course. Zero makes this candidate score exactly like `dwa` plus "
            "the predicted-clearance term, which is the cheapest way to ask what "
            "this one term is worth."
        ),
    )


class DWAPredictivePlanner(LocalPlanner):
    """Deterministic DWA scoring trajectories against a moving world."""

    def __init__(
        self,
        config: DWAPredictiveConfig | None = None,
        provider: TrackProvider | None = None,
    ) -> None:
        self._config = config or DWAPredictiveConfig()
        self._provider = provider
        self._robot: RobotConfig | None = None
        self._envelope = SafetyEnvelope()
        self._obstacle_speed = 0.0
        self._path: tuple[Point2D, ...] = ()
        self._path_index = 0
        self._previous: SimAction | None = None

    @property
    def name(self) -> str:
        return "dwa_predictive"

    @property
    def control_period(self) -> float:
        return self._config.control_period

    @property
    def config(self) -> DWAPredictiveConfig:
        return self._config

    def reset(
        self,
        global_path: Sequence[Point2D],
        robot: RobotConfig,
        envelope: SafetyEnvelope | None = None,
        obstacle_speed: float | None = None,
    ) -> None:
        """Adopt a path, and be told what the deployment declares.

        Same two deployment-owned arguments as ``dwa``, arriving the same
        way and meaning the same thing — see
        :meth:`~planbench_planning.dwa.planner.DWAPlanner.reset`. They are
        repeated rather than inherited because this controller is a
        separate candidate, and a shared implementation is exactly the
        coupling the module docstring refuses.

        Resetting clears the previous command. A tracker will hold more
        state than that from P5, and its ``reset`` has to clear all of it
        — running two episodes on one instance must equal running two
        instances, which is a test there.
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
        robot, config = self._robot, self._config

        local_goal = self._advance_local_goal(state)
        obstacles = obstacle_points(observation)
        candidates = self._dynamic_window(state, obstacles)
        rollouts, clearances = rollout_batch(
            state, candidates, obstacles, config.horizon_seconds, config.horizon_dt
        )

        # The tracks are read once per control step, not once per
        # candidate: they describe the world, and the world does not
        # depend on which velocity the robot is considering.
        tracks = tuple(self._provider(observation.time)) if self._provider is not None else ()
        predicted_clearances, time_to_collision = self._predict(rollouts, tracks)

        # **Unchanged from `dwa`, and the reason is contract L2.** This
        # refusal reads `clearances` — the distance to the returns the
        # LiDAR gave *at this instant* — not the predicted ones. Swapping
        # in the prediction would make a longer `prediction_horizon_seconds`
        # produce a *smaller* feasible set, which is a candidate parameter
        # narrowing the set the global planner planned against.
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
                velocity,
                omega,
                trajectory,
                float(clearances[index]),
                float(predicted_clearances[index]),
                float(time_to_collision[index]),
                local_goal,
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

    def _predict(
        self, rollouts: np.ndarray, tracks: Sequence[ObstacleTrack]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Space-time clearance and time-to-collision per candidate.

        Returns ``(predicted_clearances, time_to_collision)``, both shape
        ``(N,)``. With no tracks the first is ``+inf`` and the second is
        ``+inf``, and :meth:`_score` turns both into a cost of exactly
        zero — the switch that makes this candidate reduce to ``dwa`` on a
        world with nothing moving in it.

        **The time axis is the whole trick, and it is off by one from the
        obvious.** ``rollout_batch`` returns column ``k`` as the pose
        after ``k + 1`` steps, so the obstacles must be advanced by
        ``(k + 1) · horizon_dt`` — see
        :func:`~planbench_planning.common.dwa_core.rollout_times`. Using
        ``k · horizon_dt`` predicts a world one step stale, which is a
        controller that reacts a beat late and no aggregate metric would
        show it.

        Cost note for gate G4: the broadcast below produces the same
        ``(N, K, M, 2)`` tensor the static comparison already builds, so
        the heaviest operation does not grow. What grows is ``M`` — but
        ``M`` here is the number of *tracked objects*, a handful, not the
        number of LiDAR returns.
        """
        candidates = rollouts.shape[0]
        if not tracks:
            infinite = np.full(candidates, math.inf)
            return infinite, infinite

        config = self._config
        times = rollout_times(config.horizon_seconds, config.horizon_dt)
        # Prediction may be shorter than the rollout, never longer:
        # extrapolating past the trajectory being scored would be
        # describing a robot that is not there. Clamping the *time* rather
        # than dropping columns keeps the shapes aligned with `rollouts`.
        times = np.minimum(times, config.prediction_horizon_seconds)

        centers = np.array([[track.center.x, track.center.y] for track in tracks], dtype=float)
        velocities = np.array(
            [[track.velocity.x, track.velocity.y] for track in tracks], dtype=float
        )
        radii = np.array([track.radius for track in tracks], dtype=float)

        # (K, M, 2): where each track is at each rollout column.
        predicted = centers[None, :, :] + velocities[None, :, :] * times[:, None, None]
        # (N, K, 2) - (1, K, M, 2) -> (N, K, M)
        diff = rollouts[:, :, None, :] - predicted[None, :, :, :]
        surface = np.sqrt(np.einsum("nkmd,nkmd->nkm", diff, diff)) - radii[None, None, :]

        predicted_clearance = surface.min(axis=(1, 2))

        # Time to collision: the first column at which any track would be
        # inside the hard clearance if both held course. Not a refusal —
        # `keep_out` has already done the refusing on measured points —
        # but the soft price of arriving somewhere at the same moment as
        # something else.
        assert self._robot is not None
        breach = surface.min(axis=2) <= hard_clearance(self._robot, self._envelope)
        first = np.where(breach.any(axis=1), breach.argmax(axis=1), -1)
        ttc = np.where(first >= 0, times[np.clip(first, 0, None)], math.inf)
        return predicted_clearance, ttc

    def _dynamic_window(
        self, state: RobotState, obstacles: np.ndarray
    ) -> list[tuple[float, float]]:
        """Reachable (v, w) pairs on a deterministic sample grid.

        **Identical to** ``dwa``, including the admissible-speed bound,
        and a test asserts the two produce the same window for the same
        state. Prediction does not widen it: that would be an estimate
        relaxing a hard constraint, which is the one thing this candidate
        may not do.
        """
        assert self._robot is not None
        robot, config = self._robot, self._config
        v_min, v_max, w_min, w_max = reachable_window(
            state, robot, config.control_period, config.allow_reverse
        )
        to_goal = math.hypot(self._path[-1].x - state.pose.x, self._path[-1].y - state.pose.y)
        to_obstacle = self._nearest_obstacle_distance(obstacles, state)
        headroom = max(0.0, min(to_goal, to_obstacle))
        stopping_limit = self._speed_that_stops_within(headroom, robot)
        v_max = min(v_max, stopping_limit)
        v_min = min(v_min, v_max)
        return sample_window(
            v_min, v_max, w_min, w_max, config.velocity_samples, config.omega_samples
        )

    def _score(
        self,
        velocity: float,
        omega: float,
        trajectory: Sequence[Point2D],
        clearance: float,
        predicted_clearance: float,
        time_to_collision: float,
        local_goal: Point2D,
    ) -> dict[str, float]:
        """``dwa``'s cost, plus two terms that are zero without tracks.

        The two additions are deliberately few. The plan listed a third —
        a penalty for cutting across the face of an approaching obstacle —
        and it is **not** a separate term here, because time-to-collision
        already is that measurement: a trajectory crossing in front of
        something arriving is exactly a trajectory with a short time to
        collision. A third weight with no failure mode of its own would be
        a knob to tune rather than a thing to measure.
        """
        assert self._robot is not None
        robot, config = self._robot, self._config
        end = trajectory[-1]

        approach = math.atan2(local_goal.y - end.y, local_goal.x - end.x)
        end_theta = final_heading(trajectory)
        heading = abs(normalize_angle(approach - end_theta)) / math.pi
        goal_distance = (
            math.hypot(local_goal.x - end.x, local_goal.y - end.y) / config.lookahead_distance
        )
        path_distance = distance_to_polyline(end, self._path) / config.path_distance_scale

        wanted = hard_clearance(robot, self._envelope) + config.safety_margin
        shortfall = max(0.0, wanted - clearance) / max(config.safety_margin, EPS)
        comfort = min(1.0, shortfall) ** 2
        usable = min(max(clearance - robot.radius, 0.0), config.clearance_cap)
        clearance_cost = 1.0 - usable / config.clearance_cap
        velocity_cost = 1.0 - abs(velocity) / robot.max_linear_velocity

        # Predicted clearance, scored on the same scale as the measured
        # one so the two are readable side by side. Infinite clearance —
        # no tracks at all — gives usable == cap and a cost of exactly
        # zero, which is what makes an empty world reduce to `dwa`.
        predicted_usable = min(max(predicted_clearance - robot.radius, 0.0), config.clearance_cap)
        predicted_cost = 1.0 - predicted_usable / config.clearance_cap
        # Imminent is expensive, far is cheap, never is free. Scaled by
        # the horizon so the term does not change meaning when a
        # candidate looks further ahead.
        if math.isfinite(time_to_collision):
            urgency = 1.0 - min(time_to_collision, config.horizon_seconds) / config.horizon_seconds
        else:
            urgency = 0.0

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
            "comfort": config.weight_clearance * comfort,
            # Shares `weight_clearance` with the two terms above because
            # it is the same wish measured on the future; a separate
            # weight would let a candidate care more about predicted room
            # than real room, which is not a preference anybody holds.
            "predicted_clearance": config.weight_clearance * predicted_cost,
            "time_to_collision": config.weight_time_to_collision * urgency,
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

        Measured points only — the tracks are not consulted here. This
        feeds the admissible-speed bound, which is layer 2, and layer 2
        does not take estimates.
        """
        assert self._robot is not None
        if obstacles.size == 0:
            return math.inf
        deltas = obstacles - np.array([state.pose.x, state.pose.y])
        nearest = float(np.hypot(deltas[:, 0], deltas[:, 1]).min())
        return max(0.0, nearest - hard_clearance(self._robot, self._envelope))

    def _speed_that_stops_within(self, headroom: float, robot: RobotConfig) -> float:
        """The layer-2 bound, unchanged and unshared with the prediction."""
        return admissible_speed(headroom, robot, self._config.control_period, self._obstacle_speed)
