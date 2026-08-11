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


class SensorNoise(BaseModel):
    """How badly this deployment's robot measures and executes.

    A property of the **deployment** — the site and the vehicle being
    deployed there — never of the candidate. A candidate allowed to
    declare its own noise amplitude would be choosing its own exam.

    Both amplitudes default to zero, so every profile written before this
    existed keeps its behaviour to the last float, and switching noise on
    is a deliberate change visible in the profile and on the manifest.
    Turning it on is *correcting a simulator that was more optimistic
    than reality*, and it should be expected to make results worse.

    Amplitudes follow the noise-axis table of the topic document (N5):
    LiDAR sigma 2 cm, wheel slip 2%.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    lidar_range_sigma_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Std-dev of per-ray range error, metres. Measurement only: it "
        "reaches Observation and never the collision test.",
    )
    wheel_slip_fraction: float = Field(
        default=0.0,
        ge=0.0,
        lt=1.0,
        description="Std-dev of the gap between commanded and delivered velocity, as "
        "a fraction. This one does change the real motion — the robot really slipped.",
    )

    @property
    def active(self) -> bool:
        return self.lidar_range_sigma_m > 0.0 or self.wheel_slip_fraction > 0.0
