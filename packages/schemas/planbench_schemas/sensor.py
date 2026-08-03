"""Sensor configuration schemas."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field


class LidarConfig(BaseModel):
    """Planar LiDAR configuration.

    Ray ``i`` (0-based) points at relative angle
    ``-angle_span / 2 + i * angle_span / num_rays`` from the robot
    heading, so a full 2*pi span covers the circle without duplicating
    the first ray at the end.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    num_rays: int = Field(gt=0, description="Number of evenly spaced rays.")
    max_range: float = Field(gt=0, description="Maximum measurable range in metres.")
    angle_span: float = Field(
        default=2 * math.pi,
        gt=0,
        le=2 * math.pi,
        description="Total angular coverage in radians, centred on the robot heading.",
    )
