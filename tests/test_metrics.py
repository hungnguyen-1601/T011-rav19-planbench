"""Tests for episode metric computation."""

from __future__ import annotations

import math

import pytest

from planbench_metrics import compute_episode_metrics
from planbench_schemas.episode import EpisodeResult, EpisodeStatus, TrajectoryPoint
from planbench_simulator.grid import OccupancyGrid


def tp(time: float, x: float, y: float, theta: float = 0.0, v: float = 1.0) -> TrajectoryPoint:
    return TrajectoryPoint(
        time=time, x=x, y=y, theta=theta, linear_velocity=v, angular_velocity=0.0
    )


def make_result(status: EpisodeStatus, points: list[TrajectoryPoint]) -> EpisodeResult:
    return EpisodeResult(
        status=status,
        reason="test",
        elapsed_time=points[-1].time if points else 0.0,
        steps=max(0, len(points) - 1),
        trajectory=tuple(points),
        events=(),
    )


class TestBasicMetrics:
    def test_straight_line(self) -> None:
        result = make_result(
            EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0, v=0.0), tp(1.0, 1.0, 0.0), tp(2.0, 2.0, 0.0)]
        )
        metrics = compute_episode_metrics(result, planned_path_length=1.8)
        assert metrics.trajectory_length == pytest.approx(2.0)
        assert metrics.travel_time == 2.0
        assert metrics.average_speed == pytest.approx(1.0)
        assert metrics.max_speed == 1.0
        assert metrics.smoothness == 0.0
        assert metrics.success
        assert not metrics.collision
        assert metrics.path_efficiency == pytest.approx(0.9)

    def test_smoothness_counts_heading_change(self) -> None:
        result = make_result(
            EpisodeStatus.SUCCESS,
            [tp(0.0, 0.0, 0.0, theta=0.0), tp(1.0, 1.0, 0.0, theta=math.pi / 2)],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.smoothness == pytest.approx((math.pi / 2) / 1.0)

    def test_empty_trajectory_safe(self) -> None:
        result = make_result(EpisodeStatus.NO_GLOBAL_PATH, [])
        metrics = compute_episode_metrics(result)
        assert metrics.trajectory_length == 0.0
        assert metrics.average_speed == 0.0
        assert metrics.smoothness == 0.0
        assert metrics.max_speed == 0.0
        assert metrics.path_efficiency is None

    def test_collision_flag(self) -> None:
        result = make_result(EpisodeStatus.COLLISION, [tp(0.0, 0.0, 0.0)])
        metrics = compute_episode_metrics(result)
        assert metrics.collision
        assert not metrics.success

    def test_efficiency_requires_success(self) -> None:
        result = make_result(EpisodeStatus.TIMEOUT, [tp(0.0, 0.0, 0.0), tp(1.0, 1.0, 0.0)])
        metrics = compute_episode_metrics(result, planned_path_length=1.0)
        assert metrics.path_efficiency is None


class TestClearanceMetrics:
    def test_clearance_in_empty_grid(self, empty_grid: OccupancyGrid) -> None:
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 2.5, 2.5)])
        metrics = compute_episode_metrics(result, grid=empty_grid, robot_radius=0.5)
        # Only the map boundary: 2.5 m to each edge minus the radius.
        assert metrics.min_clearance == pytest.approx(2.0)
        assert metrics.mean_clearance == pytest.approx(2.0)

    def test_clearance_requires_grid_and_radius(self) -> None:
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 2.5, 2.5)])
        metrics = compute_episode_metrics(result)
        assert metrics.min_clearance is None
        assert metrics.mean_clearance is None

    def test_clearance_tracks_nearest_obstacle(self, mixed_grid: OccupancyGrid) -> None:
        # Occupied cell box [2,3]x[2,3]; point (2.5, 1.5) is 0.5 from its face.
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 2.5, 1.5)])
        metrics = compute_episode_metrics(result, grid=mixed_grid, robot_radius=0.2)
        assert metrics.min_clearance == pytest.approx(0.3)
