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
        assert metrics.smoothness_per_metre == 0.0
        assert metrics.success
        assert not metrics.collision
        assert metrics.path_efficiency == pytest.approx(0.9)

    def test_smoothness_is_sum_of_squared_heading_changes(self) -> None:
        """spec section 8.2's literal formula: Σ(Δθ_i)², unnormalized."""
        result = make_result(
            EpisodeStatus.SUCCESS,
            [tp(0.0, 0.0, 0.0, theta=0.0), tp(1.0, 1.0, 0.0, theta=math.pi / 2)],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.smoothness == pytest.approx((math.pi / 2) ** 2)

    def test_smoothness_per_metre_is_the_length_normalized_variant(self) -> None:
        """The pre-Phase-3a formula, kept for leaderboard scoring — see
        episode_metrics.py's module docstring for why both exist."""
        result = make_result(
            EpisodeStatus.SUCCESS,
            [tp(0.0, 0.0, 0.0, theta=0.0), tp(1.0, 1.0, 0.0, theta=math.pi / 2)],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.smoothness_per_metre == pytest.approx((math.pi / 2) / 1.0)

    def test_two_turns_accumulate_in_the_raw_formula(self) -> None:
        """Σ(Δθ)² for two turns is not the same as (Σ|Δθ|)² — each turn
        is squared separately, so this also distinguishes the raw
        formula from a naive "square the total" mistake."""
        result = make_result(
            EpisodeStatus.SUCCESS,
            [
                tp(0.0, 0.0, 0.0, theta=0.0),
                tp(1.0, 1.0, 0.0, theta=math.pi / 4),
                tp(2.0, 1.0, 1.0, theta=math.pi / 2),
            ],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.smoothness == pytest.approx((math.pi / 4) ** 2 + (math.pi / 4) ** 2)

    def test_empty_trajectory_safe(self) -> None:
        result = make_result(EpisodeStatus.NO_GLOBAL_PATH, [])
        metrics = compute_episode_metrics(result)
        assert metrics.trajectory_length == 0.0
        assert metrics.average_speed == 0.0
        assert metrics.smoothness == 0.0
        assert metrics.smoothness_per_metre == 0.0
        assert metrics.max_speed == 0.0
        assert metrics.path_efficiency is None
        assert metrics.stop_and_go_count == 0

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


class TestLatencyPercentiles:
    def test_none_without_latency_samples(self) -> None:
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)])
        metrics = compute_episode_metrics(result)
        assert metrics.local_planning_latency_p50 is None
        assert metrics.local_planning_latency_p95 is None
        assert metrics.local_planning_latency_p99 is None

    def test_p99_reflects_the_slow_outlier_the_mean_would_hide(self) -> None:
        """spec section 8.3: p99 matters more than the mean because one
        slow control step is enough time to run into something — the
        whole reason this metric exists."""
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)])
        latencies = [0.01] * 99 + [0.5]  # one slow step among 99 fast ones
        metrics = compute_episode_metrics(result, local_planner_latencies=latencies)
        assert metrics.mean_local_planning_latency == pytest.approx(sum(latencies) / 100)
        assert metrics.local_planning_latency_p50 == pytest.approx(0.01)
        assert metrics.local_planning_latency_p99 > metrics.mean_local_planning_latency

    def test_percentiles_are_ordered(self) -> None:
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)])
        latencies = [0.01, 0.02, 0.03, 0.04, 0.05, 0.5]
        metrics = compute_episode_metrics(result, local_planner_latencies=latencies)
        assert (
            metrics.local_planning_latency_p50
            <= metrics.local_planning_latency_p95
            <= metrics.local_planning_latency_p99
        )


class TestStopAndGo:
    def test_starting_from_rest_is_not_a_stop_and_go(self) -> None:
        """Every episode starts at v=0 — that must not count as one."""
        result = make_result(
            EpisodeStatus.SUCCESS,
            [tp(0.0, 0.0, 0.0, v=0.0), tp(1.0, 1.0, 0.0, v=1.0), tp(2.0, 2.0, 0.0, v=1.0)],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.stop_and_go_count == 0

    def test_ending_stopped_is_not_an_extra_cycle(self) -> None:
        result = make_result(
            EpisodeStatus.SUCCESS,
            [tp(0.0, 0.0, 0.0, v=1.0), tp(1.0, 1.0, 0.0, v=1.0), tp(2.0, 1.0, 0.0, v=0.0)],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.stop_and_go_count == 0

    def test_a_real_mid_journey_stop_counts_once(self) -> None:
        result = make_result(
            EpisodeStatus.SUCCESS,
            [
                tp(0.0, 0.0, 0.0, v=1.0),
                tp(1.0, 1.0, 0.0, v=0.0),  # stops mid-journey
                tp(2.0, 1.0, 0.0, v=1.0),  # resumes
            ],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.stop_and_go_count == 1

    def test_two_stops_count_twice(self) -> None:
        result = make_result(
            EpisodeStatus.SUCCESS,
            [
                tp(0.0, 0.0, 0.0, v=1.0),
                tp(1.0, 1.0, 0.0, v=0.0),
                tp(2.0, 1.0, 0.0, v=1.0),
                tp(3.0, 2.0, 0.0, v=0.0),
                tp(4.0, 2.0, 0.0, v=1.0),
            ],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.stop_and_go_count == 2
