"""Observation encoding for the RL navigation policy.

The observation is versioned (spec section 24): a policy trained on v1
cannot be evaluated under a different encoding, so the version travels
with every checkpoint.

Layout (all values normalized to roughly [-1, 1] so no input dominates
the network by scale alone):

    [0            : num_lidar_bins)  down-sampled LiDAR, range/max_range
    [bins         : bins+1)          goal distance / observation_range
    [bins+1       : bins+2)          goal bearing / pi
    [bins+2       : bins+3)          linear velocity / max_linear_velocity
    [bins+3       : bins+4)          angular velocity / max_angular_velocity
    [bins+4       : bins+4+2*K)      K lookahead waypoints in the robot
                                     frame, each (x, y) / observation_range
    [bins+4+2*K   : +1)              signed cross-track error / lane_width

The policy sees only what the robot could sense: LiDAR, its own state
and the global path it was given. Ground-truth obstacle poses are never
included — that would let a policy cheat in a way no real robot can.

LiDAR down-sampling takes the **minimum** of each bin, never the mean:
averaging can hide a single ray that detects a thin obstacle.
"""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.episode import Observation
from planbench_schemas.geometry import EPS, Point2D
from planbench_schemas.robot import RobotConfig

OBSERVATION_VERSION = "v1"


class ObservationConfig(BaseModel):
    """How raw sensor data becomes a fixed-size policy input."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    version: str = OBSERVATION_VERSION
    num_lidar_bins: int = Field(default=24, ge=4)
    num_waypoints: int = Field(default=3, ge=1, description="Lookahead waypoints in robot frame.")
    waypoint_spacing: float = Field(default=0.8, gt=0, description="Metres between lookaheads.")
    observation_range: float = Field(
        default=6.0, gt=0, description="Distances are normalized by this, then clipped."
    )
    lane_width: float = Field(default=1.5, gt=0, description="Normalizer for cross-track error.")

    @property
    def size(self) -> int:
        return self.num_lidar_bins + 4 + 2 * self.num_waypoints + 1


def downsample_lidar(ranges: tuple[float, ...], bins: int, max_range: float) -> np.ndarray:
    """Reduce a scan to ``bins`` values using the minimum in each bin.

    Minimum, not mean: a single ray hitting a table leg must survive
    down-sampling, otherwise the policy is blind to thin obstacles.
    """
    if not ranges:
        return np.ones(bins, dtype=np.float32)
    values = np.asarray(ranges, dtype=np.float32)
    # np.array_split handles a ray count that is not a multiple of bins.
    return np.array(
        [chunk.min() / max_range for chunk in np.array_split(values, bins)], dtype=np.float32
    )


def lookahead_waypoints(
    path: tuple[Point2D, ...], position: Point2D, theta: float, config: ObservationConfig
) -> list[tuple[float, float]]:
    """K points ahead on the path, expressed in the robot frame.

    Robot frame, not world frame: the policy must generalise across maps,
    and a world-frame goal would tie it to specific coordinates.
    """
    if not path:
        return [(0.0, 0.0)] * config.num_waypoints
    closest_index = min(
        range(len(path)),
        key=lambda index: math.hypot(path[index].x - position.x, path[index].y - position.y),
    )
    cumulative = _cumulative_lengths(path)
    base = cumulative[closest_index]
    points: list[tuple[float, float]] = []
    for step in range(1, config.num_waypoints + 1):
        target = base + step * config.waypoint_spacing
        world = _point_at_arclength(path, cumulative, target)
        dx, dy = world.x - position.x, world.y - position.y
        cos_theta, sin_theta = math.cos(-theta), math.sin(-theta)
        points.append((dx * cos_theta - dy * sin_theta, dx * sin_theta + dy * cos_theta))
    return points


def cross_track_error(path: tuple[Point2D, ...], position: Point2D) -> float:
    """Signed distance from the path (left of travel is positive)."""
    if len(path) < 2:
        return 0.0
    best = math.inf
    signed = 0.0
    for a, b in zip(path, path[1:], strict=False):
        dx, dy = b.x - a.x, b.y - a.y
        length_squared = dx * dx + dy * dy
        if length_squared <= EPS:
            continue
        t = max(0.0, min(1.0, ((position.x - a.x) * dx + (position.y - a.y) * dy) / length_squared))
        closest_x, closest_y = a.x + t * dx, a.y + t * dy
        distance = math.hypot(position.x - closest_x, position.y - closest_y)
        if distance < best:
            best = distance
            # Cross product sign tells which side of the segment we are on.
            signed = math.copysign(distance, dx * (position.y - a.y) - dy * (position.x - a.x))
    return 0.0 if best is math.inf else signed


def encode(
    observation: Observation,
    path: tuple[Point2D, ...],
    robot: RobotConfig,
    lidar_max_range: float,
    config: ObservationConfig,
) -> np.ndarray:
    """Build the fixed-size policy input. Always finite, always clipped."""
    features: list[float] = []
    features.extend(
        downsample_lidar(observation.lidar_ranges, config.num_lidar_bins, lidar_max_range).tolist()
    )
    features.append(min(observation.goal_distance / config.observation_range, 1.0))
    features.append(observation.goal_bearing / math.pi)
    features.append(observation.linear_velocity / robot.max_linear_velocity)
    features.append(observation.angular_velocity / robot.max_angular_velocity)
    for x, y in lookahead_waypoints(
        path, observation.pose.position, observation.pose.theta, config
    ):
        features.append(x / config.observation_range)
        features.append(y / config.observation_range)
    features.append(cross_track_error(path, observation.pose.position) / config.lane_width)

    vector = np.asarray(features, dtype=np.float32)
    # A NaN reaching the network would poison training silently.
    vector = np.nan_to_num(vector, nan=0.0, posinf=1.0, neginf=-1.0)
    return np.clip(vector, -1.0, 1.0)


def _cumulative_lengths(path: tuple[Point2D, ...]) -> list[float]:
    lengths = [0.0]
    for a, b in zip(path, path[1:], strict=False):
        lengths.append(lengths[-1] + math.hypot(b.x - a.x, b.y - a.y))
    return lengths


def _point_at_arclength(
    path: tuple[Point2D, ...], cumulative: list[float], target: float
) -> Point2D:
    if target <= 0:
        return path[0]
    if target >= cumulative[-1]:
        return path[-1]
    for index in range(len(path) - 1):
        if cumulative[index + 1] >= target:
            span = cumulative[index + 1] - cumulative[index]
            t = (target - cumulative[index]) / span if span > EPS else 0.0
            a, b = path[index], path[index + 1]
            return Point2D(x=a.x + (b.x - a.x) * t, y=a.y + (b.y - a.y) * t)
    return path[-1]
