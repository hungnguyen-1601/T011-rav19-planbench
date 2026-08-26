"""2D geometry primitives shared across all PlanBench components.

Units follow SI everywhere: metres for distance, seconds for time,
radians for angles. Angles are normalized to the half-open interval
(-pi, pi].
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, field_validator

# Project-wide tolerance for float comparisons (see docs/architecture.md).
EPS = 1e-9

_TWO_PI = 2.0 * math.pi


def normalize_angle(theta: float) -> float:
    """Normalize an angle in radians to the interval (-pi, pi].

    Raises:
        ValueError: If ``theta`` is NaN or infinite.
    """
    if not math.isfinite(theta):
        raise ValueError(f"theta must be finite, got {theta!r}")
    normalized = theta % _TWO_PI  # in [0, 2*pi)
    if normalized > math.pi:
        normalized -= _TWO_PI
    return normalized


class Point2D(BaseModel):
    """Immutable point in the world frame, in metres."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    x: float
    y: float


class Pose2D(BaseModel):
    """Immutable 2D pose: position in metres, heading in radians.

    ``theta`` is normalized to (-pi, pi] at validation time.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    x: float
    y: float
    theta: float = 0.0

    @field_validator("theta")
    @classmethod
    def _normalize_theta(cls, value: float) -> float:
        return normalize_angle(value)

    @property
    def position(self) -> Point2D:
        return Point2D(x=self.x, y=self.y)


def euclidean_distance(a: Point2D, b: Point2D) -> float:
    """Euclidean distance between two points, in metres."""
    return math.hypot(a.x - b.x, a.y - b.y)


def distance_point_to_aabb(
    px: float, py: float, min_x: float, min_y: float, max_x: float, max_y: float
) -> float:
    """Distance from a point to an axis-aligned rectangle (0 if inside)."""
    closest_x = min(max(px, min_x), max_x)
    closest_y = min(max(py, min_y), max_y)
    return math.hypot(px - closest_x, py - closest_y)
