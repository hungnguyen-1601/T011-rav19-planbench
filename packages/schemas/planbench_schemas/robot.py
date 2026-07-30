"""Robot configuration, state and action schemas.

The MVP robot footprint is a circle described by ``RobotConfig.radius``.
All limits live in the config; simulator logic must never hardcode
them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.geometry import Pose2D


class RobotConfig(BaseModel):
    """Physical limits of a circular differential-drive robot."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    radius: float = Field(gt=0, description="Footprint radius in metres.")
    max_linear_velocity: float = Field(gt=0, description="Absolute linear velocity bound, m/s.")
    max_angular_velocity: float = Field(gt=0, description="Absolute angular velocity bound, rad/s.")
    max_linear_acceleration: float = Field(gt=0, description="Linear acceleration bound, m/s^2.")
    max_angular_acceleration: float = Field(gt=0, description="Angular accel. bound, rad/s^2.")


class RobotState(BaseModel):
    """Instantaneous robot state in the world frame."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    pose: Pose2D
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0


class SimAction(BaseModel):
    """Commanded target velocities.

    Values are requests; clamping to the robot's velocity and
    acceleration limits is the responsibility of the kinematics layer,
    not of this schema.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    linear_velocity: float
    angular_velocity: float
