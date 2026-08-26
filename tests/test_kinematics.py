"""Tests for differential-drive kinematics (explicit Euler)."""

from __future__ import annotations

import math

import pytest

from planbench_schemas.geometry import Pose2D, normalize_angle
from planbench_schemas.robot import RobotConfig, RobotState, SimAction
from planbench_simulator.kinematics import clamp, step


def _unconstrained_config() -> RobotConfig:
    """Limits high enough that clamping never binds in pure-motion tests."""
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=10.0,
        max_angular_velocity=10.0,
        max_linear_acceleration=1000.0,
        max_angular_acceleration=1000.0,
    )


def _state(x: float = 0.0, y: float = 0.0, theta: float = 0.0, v: float = 0.0, w: float = 0.0):
    return RobotState(pose=Pose2D(x=x, y=y, theta=theta), linear_velocity=v, angular_velocity=w)


class TestClamp:
    def test_within_interval(self) -> None:
        assert clamp(0.5, 0.0, 1.0) == 0.5

    def test_below_and_above(self) -> None:
        assert clamp(-2.0, 0.0, 1.0) == 0.0
        assert clamp(2.0, 0.0, 1.0) == 1.0

    def test_invalid_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="clamp interval"):
            clamp(0.0, 1.0, -1.0)


class TestPureMotion:
    def test_straight_line_along_x(self) -> None:
        config = _unconstrained_config()
        state = _state(v=0.5)
        action = SimAction(linear_velocity=0.5, angular_velocity=0.0)
        for _ in range(10):
            state = step(state, action, config, dt=0.1)
        assert state.pose.x == pytest.approx(0.5, abs=1e-12)
        assert state.pose.y == 0.0
        assert state.pose.theta == 0.0

    def test_straight_line_along_heading(self) -> None:
        config = _unconstrained_config()
        theta = math.pi / 4
        state = _state(theta=theta, v=1.0)
        action = SimAction(linear_velocity=1.0, angular_velocity=0.0)
        for _ in range(10):
            state = step(state, action, config, dt=0.1)
        expected = 1.0 * math.cos(theta)  # = sin(theta)
        assert state.pose.x == pytest.approx(expected, abs=1e-12)
        assert state.pose.y == pytest.approx(expected, abs=1e-12)

    def test_rotate_in_place(self) -> None:
        config = _unconstrained_config()
        state = _state(x=1.0, y=2.0, w=1.0)
        action = SimAction(linear_velocity=0.0, angular_velocity=1.0)
        for _ in range(5):
            state = step(state, action, config, dt=0.1)
        assert state.pose.x == 1.0
        assert state.pose.y == 2.0
        assert state.pose.theta == pytest.approx(0.5, abs=1e-12)

    def test_theta_wraps_into_half_open_interval(self) -> None:
        config = _unconstrained_config()
        state = _state(theta=3.0, w=1.0)
        action = SimAction(linear_velocity=0.0, angular_velocity=1.0)
        state = step(state, action, config, dt=0.5)
        assert state.pose.theta == pytest.approx(3.5 - 2 * math.pi, abs=1e-12)
        assert -math.pi < state.pose.theta <= math.pi

    def test_arc_matches_stepwise_euler_reference(self) -> None:
        """Arc motion must equal the per-step Euler recurrence (NOT the
        continuous analytic arc), per the project specification."""
        config = _unconstrained_config()
        v, w, dt, steps = 0.5, 1.0, 0.05, 40
        state = _state(v=v, w=w)
        action = SimAction(linear_velocity=v, angular_velocity=w)

        # Independent Euler reference computed inside the test.
        ref_x, ref_y, ref_theta = 0.0, 0.0, 0.0
        for _ in range(steps):
            state = step(state, action, config, dt=dt)
            ref_x += v * math.cos(ref_theta) * dt
            ref_y += v * math.sin(ref_theta) * dt
            ref_theta = normalize_angle(ref_theta + w * dt)

        assert state.pose.x == pytest.approx(ref_x, abs=1e-12)
        assert state.pose.y == pytest.approx(ref_y, abs=1e-12)
        assert state.pose.theta == pytest.approx(ref_theta, abs=1e-12)


class TestLimits:
    def test_linear_velocity_clamped_to_config(self, robot_config: RobotConfig) -> None:
        state = _state(v=robot_config.max_linear_velocity)
        action = SimAction(linear_velocity=100.0, angular_velocity=0.0)
        new_state = step(state, action, robot_config, dt=0.1)
        assert new_state.linear_velocity == robot_config.max_linear_velocity

    def test_angular_velocity_clamped_to_config(self, robot_config: RobotConfig) -> None:
        state = _state(w=-robot_config.max_angular_velocity)
        action = SimAction(linear_velocity=0.0, angular_velocity=-100.0)
        new_state = step(state, action, robot_config, dt=0.1)
        assert new_state.angular_velocity == -robot_config.max_angular_velocity

    def test_acceleration_limit_from_rest(self, robot_config: RobotConfig) -> None:
        # a_max = 1.0 m/s^2, dt = 0.1 s -> velocity may grow by at most 0.1 per step.
        state = _state()
        action = SimAction(linear_velocity=1.0, angular_velocity=0.0)
        state = step(state, action, robot_config, dt=0.1)
        assert state.linear_velocity == pytest.approx(0.1, abs=1e-12)
        assert state.pose.x == pytest.approx(0.01, abs=1e-12)
        state = step(state, action, robot_config, dt=0.1)
        assert state.linear_velocity == pytest.approx(0.2, abs=1e-12)
        assert state.pose.x == pytest.approx(0.03, abs=1e-12)

    def test_deceleration_is_also_limited(self, robot_config: RobotConfig) -> None:
        state = _state(v=1.0)
        action = SimAction(linear_velocity=0.0, angular_velocity=0.0)
        new_state = step(state, action, robot_config, dt=0.1)
        assert new_state.linear_velocity == pytest.approx(0.9, abs=1e-12)

    def test_angular_acceleration_limit(self, robot_config: RobotConfig) -> None:
        # alpha_max = 2.0 rad/s^2, dt = 0.1 s -> omega may change by at most 0.2.
        state = _state()
        action = SimAction(linear_velocity=0.0, angular_velocity=2.0)
        new_state = step(state, action, robot_config, dt=0.1)
        assert new_state.angular_velocity == pytest.approx(0.2, abs=1e-12)


class TestValidationAndDeterminism:
    @pytest.mark.parametrize("bad_dt", [0.0, -0.1, math.nan, math.inf])
    def test_invalid_dt_raises(self, robot_config: RobotConfig, bad_dt: float) -> None:
        state = _state()
        action = SimAction(linear_velocity=0.5, angular_velocity=0.0)
        with pytest.raises(ValueError, match="dt"):
            step(state, action, robot_config, dt=bad_dt)

    def test_deterministic_for_identical_inputs(self, robot_config: RobotConfig) -> None:
        state = _state(x=0.3, y=-0.2, theta=1.1, v=0.4, w=-0.3)
        action = SimAction(linear_velocity=0.9, angular_velocity=0.7)
        first = step(state, action, robot_config, dt=0.05)
        second = step(state, action, robot_config, dt=0.05)
        assert first == second
