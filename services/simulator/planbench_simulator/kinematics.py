"""Differential-drive kinematics with explicit Euler integration.

Update order per step (documented contract, tested in
tests/test_kinematics.py):

1. Clamp the commanded velocities to the robot's velocity limits.
2. Limit the velocity change from the current state by
   ``max_acceleration * dt``.
3. Integrate the pose with the resulting velocities (explicit Euler,
   exactly as specified for the project):

   x_new     = x + v * cos(theta) * dt
   y_new     = y + v * sin(theta) * dt
   theta_new = normalize_angle(theta + omega * dt)

All functions are pure and deterministic.
"""

from __future__ import annotations

import math

from planbench_schemas.geometry import Pose2D, normalize_angle
from planbench_schemas.robot import RobotConfig, RobotState, SimAction


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the closed interval [low, high]."""
    if low > high:
        raise ValueError(f"invalid clamp interval [{low}, {high}]")
    return max(low, min(high, value))


def step(state: RobotState, action: SimAction, config: RobotConfig, dt: float) -> RobotState:
    """Advance the robot by one time step of ``dt`` seconds.

    Raises:
        ValueError: If ``dt`` is not a finite positive number.
    """
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError(f"dt must be a finite positive number, got {dt!r}")

    target_v = clamp(
        action.linear_velocity, -config.max_linear_velocity, config.max_linear_velocity
    )
    target_w = clamp(
        action.angular_velocity, -config.max_angular_velocity, config.max_angular_velocity
    )

    max_dv = config.max_linear_acceleration * dt
    max_dw = config.max_angular_acceleration * dt
    v = clamp(target_v, state.linear_velocity - max_dv, state.linear_velocity + max_dv)
    w = clamp(target_w, state.angular_velocity - max_dw, state.angular_velocity + max_dw)

    pose = state.pose
    new_pose = Pose2D(
        x=pose.x + v * math.cos(pose.theta) * dt,
        y=pose.y + v * math.sin(pose.theta) * dt,
        theta=normalize_angle(pose.theta + w * dt),
    )
    return RobotState(pose=new_pose, linear_velocity=v, angular_velocity=w)
