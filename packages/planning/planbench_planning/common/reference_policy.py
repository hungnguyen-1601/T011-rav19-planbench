"""A monolithic policy with no weights, for testing the adapter.

**Never a candidate.** This exists so the end-to-end path has something
real to drive, the way ``PurePursuitLocalPlanner`` exists so the modular
path does (decision D12). It is not registered, not benchmarkable, and
comparing it against a trained stack would compare a trained stack
against nine lines of trigonometry.

What it does: steer at the goal, and slow down when the scan says
something is close ahead. That is enough to prove the loop runs a
candidate that never sees a global path — which is the property under
test — and deliberately not enough to be interesting.
"""

from __future__ import annotations

import math
import time

from planbench_planning.common.local_base import LocalPlanResult
from planbench_planning.common.policy_base import MonolithicPolicy
from planbench_schemas.episode import Observation
from planbench_schemas.robot import RobotConfig, RobotState, SimAction

__all__ = ["GreedyReferencePolicy"]

#: Rays within this angle of straight ahead count as "in the way".
_AHEAD_RAD = math.pi / 6
#: Below this clearance the policy stops advancing and only turns.
_STOP_DISTANCE_M = 0.8


class GreedyReferencePolicy(MonolithicPolicy):
    """Turn toward the goal; creep when the way ahead is close."""

    def __init__(self) -> None:
        self._robot: RobotConfig | None = None

    @property
    def name(self) -> str:
        return "greedy_reference_policy"

    def prepare(self, robot: RobotConfig) -> None:
        self._robot = robot

    def decide(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        started = time.perf_counter()
        robot = self._robot
        assert robot is not None, "reset() must run before decide()"

        bearing = observation.goal_bearing
        angular = max(
            -robot.max_angular_velocity,
            min(robot.max_angular_velocity, 2.0 * bearing),
        )

        # The nearest return within a cone straight ahead. Rays are
        # centred on the heading, so the middle of the scan is forward.
        ranges = observation.lidar_ranges
        linear = robot.max_linear_velocity
        if ranges:
            span = len(ranges)
            middle = span // 2
            reach = max(1, int(_AHEAD_RAD / (2 * math.pi) * span))
            ahead = min(ranges[max(0, middle - reach) : middle + reach + 1], default=math.inf)
            if ahead < _STOP_DISTANCE_M:
                linear = 0.0
            elif abs(bearing) > math.pi / 2:
                # Facing away from the goal: turn on the spot rather than
                # drive a long arc, which on a small map is a wall.
                linear = 0.0

        return LocalPlanResult(
            action=SimAction(linear_velocity=linear, angular_velocity=angular),
            latency_seconds=time.perf_counter() - started,
        )
