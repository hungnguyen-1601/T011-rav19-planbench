"""Pure-pursuit waypoint follower.

TEMPORARY ADAPTER (decision D12): exists only so a complete A* episode
can run before DWA lands. It is NOT a benchmark local planner and must
never appear in algorithm comparisons.

Deterministic: no randomness; the only state is the monotonically
advancing target waypoint index.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.geometry import Point2D, euclidean_distance, normalize_angle
from planbench_schemas.robot import RobotConfig, RobotState, SimAction
from planbench_simulator.kinematics import clamp


class PurePursuitConfig(BaseModel):
    """Tunables for the pure-pursuit adapter."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    lookahead_distance: float = Field(default=0.6, gt=0)
    heading_gain: float = Field(default=2.5, gt=0)
    slowdown_distance: float = Field(default=0.8, gt=0)


class PurePursuitFollower:
    """Track a world-frame polyline with simple pure pursuit."""

    def __init__(
        self,
        path: Sequence[Point2D],
        robot: RobotConfig,
        config: PurePursuitConfig | None = None,
    ) -> None:
        if not path:
            raise ValueError("path must contain at least one point")
        self._path = tuple(path)
        self._robot = robot
        self._config = config or PurePursuitConfig()
        self._target_index = 0

    @property
    def target_index(self) -> int:
        return self._target_index

    def compute_action(self, state: RobotState) -> SimAction:
        """Velocity command steering toward the current lookahead target."""
        position = state.pose.position
        last = len(self._path) - 1
        # Skip waypoints the robot has effectively passed...
        while self._target_index < last and euclidean_distance(
            position, self._path[self._target_index + 1]
        ) <= euclidean_distance(position, self._path[self._target_index]):
            self._target_index += 1
        # ...then advance through waypoints inside the lookahead circle.
        while (
            self._target_index < last
            and euclidean_distance(position, self._path[self._target_index])
            < self._config.lookahead_distance
        ):
            self._target_index += 1

        target = self._path[self._target_index]
        bearing = normalize_angle(
            math.atan2(target.y - position.y, target.x - position.x) - state.pose.theta
        )
        angular = clamp(
            self._config.heading_gain * bearing,
            -self._robot.max_angular_velocity,
            self._robot.max_angular_velocity,
        )
        goal_distance = euclidean_distance(position, self._path[last])
        heading_scale = max(0.0, math.cos(bearing))  # stop and turn if target is behind
        distance_scale = min(1.0, goal_distance / self._config.slowdown_distance)
        linear = self._robot.max_linear_velocity * heading_scale * distance_scale
        return SimAction(linear_velocity=linear, angular_velocity=angular)
