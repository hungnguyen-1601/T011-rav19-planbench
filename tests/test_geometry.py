"""Tests for planbench_schemas.geometry."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from planbench_schemas.geometry import Point2D, Pose2D, euclidean_distance, normalize_angle


class TestNormalizeAngle:
    @pytest.mark.parametrize(
        ("theta", "expected"),
        [
            (0.0, 0.0),
            (1.0, 1.0),
            (-1.0, -1.0),
            (math.pi, math.pi),  # upper boundary is included
            (-math.pi, math.pi),  # lower boundary maps to +pi: interval is (-pi, pi]
            (2 * math.pi, 0.0),
            (-2 * math.pi, 0.0),
            (3 * math.pi, math.pi),
            (-3 * math.pi, math.pi),
            (math.pi / 2 + 2 * math.pi, math.pi / 2),
            (-math.pi / 2 - 4 * math.pi, -math.pi / 2),
        ],
    )
    def test_known_values(self, theta: float, expected: float) -> None:
        assert normalize_angle(theta) == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize("k", range(-50, 51))
    def test_result_always_in_half_open_interval(self, k: int) -> None:
        result = normalize_angle(0.7 + k * math.pi)
        assert -math.pi < result <= math.pi

    def test_idempotent(self) -> None:
        for theta in (-7.3, -1.0, 0.0, 2.5, 9.9):
            once = normalize_angle(theta)
            assert normalize_angle(once) == once

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_rejects_non_finite(self, bad: float) -> None:
        with pytest.raises(ValueError, match="finite"):
            normalize_angle(bad)


class TestPoint2D:
    def test_creation(self) -> None:
        point = Point2D(x=1.5, y=-2.0)
        assert point.x == 1.5
        assert point.y == -2.0

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_rejects_non_finite(self, bad: float) -> None:
        with pytest.raises(ValidationError):
            Point2D(x=bad, y=0.0)
        with pytest.raises(ValidationError):
            Point2D(x=0.0, y=bad)

    def test_frozen(self) -> None:
        point = Point2D(x=0.0, y=0.0)
        with pytest.raises(ValidationError):
            point.x = 1.0  # type: ignore[misc]


class TestPose2D:
    def test_theta_normalized_at_construction(self) -> None:
        pose = Pose2D(x=0.0, y=0.0, theta=3 * math.pi)
        assert pose.theta == pytest.approx(math.pi, abs=1e-9)

    def test_theta_defaults_to_zero(self) -> None:
        assert Pose2D(x=1.0, y=2.0).theta == 0.0

    def test_position_property(self) -> None:
        pose = Pose2D(x=3.0, y=4.0, theta=1.0)
        assert pose.position == Point2D(x=3.0, y=4.0)

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_rejects_non_finite_theta(self, bad: float) -> None:
        with pytest.raises(ValidationError):
            Pose2D(x=0.0, y=0.0, theta=bad)

    def test_frozen(self) -> None:
        pose = Pose2D(x=0.0, y=0.0)
        with pytest.raises(ValidationError):
            pose.theta = 1.0  # type: ignore[misc]


class TestEuclideanDistance:
    def test_three_four_five(self) -> None:
        assert euclidean_distance(Point2D(x=0.0, y=0.0), Point2D(x=3.0, y=4.0)) == 5.0

    def test_zero_distance(self) -> None:
        point = Point2D(x=-1.2, y=3.4)
        assert euclidean_distance(point, point) == 0.0

    def test_symmetric(self) -> None:
        a = Point2D(x=1.0, y=2.0)
        b = Point2D(x=-3.0, y=0.5)
        assert euclidean_distance(a, b) == euclidean_distance(b, a)
