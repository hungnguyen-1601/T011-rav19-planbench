"""Tests for episode metric computation."""

from __future__ import annotations

import math

import pytest

from planbench_metrics import MetricConfig, compute_episode_metrics
from planbench_schemas.episode import (
    EpisodeEvent,
    EpisodeResult,
    EpisodeStatus,
    TrajectoryPoint,
)
from planbench_simulator.grid import OccupancyGrid


def tp(time: float, x: float, y: float, theta: float = 0.0, v: float = 1.0) -> TrajectoryPoint:
    return TrajectoryPoint(
        time=time, x=x, y=y, theta=theta, linear_velocity=v, angular_velocity=0.0
    )


def make_result(
    status: EpisodeStatus,
    points: list[TrajectoryPoint],
    events: tuple[EpisodeEvent, ...] = (),
) -> EpisodeResult:
    return EpisodeResult(
        status=status,
        reason="test",
        elapsed_time=points[-1].time if points else 0.0,
        steps=max(0, len(points) - 1),
        trajectory=tuple(points),
        events=events,
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
    def test_clearance_far_from_anything_is_floored_at_the_window(
        self, empty_grid: OccupancyGrid
    ) -> None:
        """Standing in the middle of an empty map reports the window.

        The true answer is 2.0 — 2.5 m to each edge minus the radius —
        and this used to assert it. The grid scan is now windowed at 2 m
        (see `clearance_to_obstacles`), because the exhaustive version
        was 90% of a test-bench episode's wall clock for a number HĐ-5's
        Metrics Engine never reads.

        **Nothing judged changes.** `min_clearance` is anchored at two
        robot radii, about 0.52 m, so 1.5 and 2.0 both score a flat 1.0.
        And the direction is the safe one: reporting less room than there
        is can only make a candidate look worse, never wave one through.
        """
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 2.5, 2.5)])
        metrics = compute_episode_metrics(result, grid=empty_grid, robot_radius=0.5)
        assert metrics.min_clearance == pytest.approx(1.5)
        assert metrics.mean_clearance == pytest.approx(1.5)

    def test_clearance_near_a_wall_is_still_exact(self, empty_grid: OccupancyGrid) -> None:
        """The other side of the boundary the test above records.

        Half a metre from the edge is well inside the window, so the
        answer is the true distance and not a floor. Without this, the
        pair above would document a cheaper computation without showing
        that it is still exact wherever the value can change a metric.
        """
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.5, 2.5)])
        metrics = compute_episode_metrics(result, grid=empty_grid, robot_radius=0.2)
        assert metrics.min_clearance == pytest.approx(0.3)

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


class TestSmoothnessSquared:
    def test_hand_computed_sum_of_squares(self) -> None:
        # Two heading changes: +pi/2 then -pi/4 -> S = (pi/2)^2 + (pi/4)^2.
        result = make_result(
            EpisodeStatus.SUCCESS,
            [
                tp(0.0, 0.0, 0.0, theta=0.0),
                tp(1.0, 1.0, 0.0, theta=math.pi / 2),
                tp(2.0, 1.0, 1.0, theta=math.pi / 4),
            ],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.smoothness_squared == pytest.approx((math.pi / 2) ** 2 + (math.pi / 4) ** 2)

    def test_straight_line_is_zero(self) -> None:
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0), tp(1.0, 1.0, 0.0)])
        assert compute_episode_metrics(result).smoothness_squared == 0.0

    def test_old_field_still_present_and_unchanged(self) -> None:
        # The deprecated rate must not silently change meaning (plan rule 7).
        result = make_result(
            EpisodeStatus.SUCCESS,
            [tp(0.0, 0.0, 0.0, theta=0.0), tp(1.0, 1.0, 0.0, theta=math.pi / 2)],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.smoothness == pytest.approx((math.pi / 2) / 1.0)
        assert metrics.smoothness_squared == pytest.approx((math.pi / 2) ** 2)

    def test_wraparound_uses_normalized_angle(self) -> None:
        # 350deg -> 10deg is a 20deg turn, not 340deg.
        result = make_result(
            EpisodeStatus.SUCCESS,
            [
                tp(0.0, 0.0, 0.0, theta=math.radians(350)),
                tp(1.0, 1.0, 0.0, theta=math.radians(10)),
            ],
        )
        metrics = compute_episode_metrics(result)
        assert metrics.smoothness_squared == pytest.approx(math.radians(20) ** 2)


class TestLatencyPercentiles:
    def test_hand_computed_percentiles(self) -> None:
        # Linear interpolation on [1..10]: p50=5.5, p95=9.55, p99=9.91.
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)])
        metrics = compute_episode_metrics(
            result, local_planner_latencies=[float(v) for v in range(1, 11)]
        )
        assert metrics.local_planning_latency_p50 == pytest.approx(5.5)
        assert metrics.local_planning_latency_p95 == pytest.approx(9.55)
        assert metrics.local_planning_latency_p99 == pytest.approx(9.91)

    def test_single_value(self) -> None:
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)])
        metrics = compute_episode_metrics(result, local_planner_latencies=[0.02])
        assert metrics.local_planning_latency_p50 == pytest.approx(0.02)
        assert metrics.local_planning_latency_p99 == pytest.approx(0.02)

    def test_no_latencies_is_none_not_zero(self) -> None:
        result = make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)])
        metrics = compute_episode_metrics(result)
        assert metrics.local_planning_latency_p50 is None
        assert metrics.local_planning_latency_p95 is None
        assert metrics.local_planning_latency_p99 is None


class TestStopAndGo:
    def test_initial_standstill_not_counted(self) -> None:
        # Standing, then accelerating once: zero stop-and-go events.
        points = [tp(0.0, 0.0, 0.0, v=0.0), tp(1.0, 0.0, 0.0, v=0.0), tp(2.0, 1.0, 0.0, v=1.0)]
        metrics = compute_episode_metrics(make_result(EpisodeStatus.SUCCESS, points))
        assert metrics.stop_and_go_count == 0

    def test_never_moved_is_zero(self) -> None:
        points = [tp(float(i), 0.0, 0.0, v=0.0) for i in range(5)]
        metrics = compute_episode_metrics(make_result(EpisodeStatus.TIMEOUT, points))
        assert metrics.stop_and_go_count == 0

    def test_stop_then_resume_counts_once(self) -> None:
        points = [
            tp(0.0, 0.0, 0.0, v=0.0),
            tp(1.0, 1.0, 0.0, v=1.0),  # moving
            tp(2.0, 1.5, 0.0, v=0.0),  # stopped
            tp(3.0, 2.5, 0.0, v=1.0),  # resumed
        ]
        metrics = compute_episode_metrics(make_result(EpisodeStatus.SUCCESS, points))
        assert metrics.stop_and_go_count == 1

    def test_two_full_cycles_count_twice(self) -> None:
        speeds = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        points = [tp(float(i), float(i), 0.0, v=v) for i, v in enumerate(speeds)]
        metrics = compute_episode_metrics(make_result(EpisodeStatus.SUCCESS, points))
        assert metrics.stop_and_go_count == 2

    def test_jitter_inside_hysteresis_band_not_counted(self) -> None:
        # Default band is [0.05, 0.10]; oscillating within it is neither a
        # stop nor a resume.
        speeds = [0.0, 1.0, 0.07, 0.09, 0.06, 0.08, 1.0]
        points = [tp(float(i), float(i), 0.0, v=v) for i, v in enumerate(speeds)]
        metrics = compute_episode_metrics(make_result(EpisodeStatus.SUCCESS, points))
        assert metrics.stop_and_go_count == 0

    def test_partial_recovery_below_resume_threshold_not_counted(self) -> None:
        # Stopped, twitching below the resume threshold: still one stop,
        # counted only when it truly resumes.
        speeds = [0.0, 1.0, 0.04, 0.07, 0.04, 0.07, 1.0]
        points = [tp(float(i), float(i), 0.0, v=v) for i, v in enumerate(speeds)]
        metrics = compute_episode_metrics(make_result(EpisodeStatus.SUCCESS, points))
        assert metrics.stop_and_go_count == 1

    def test_threshold_comes_from_config_not_hardcoded(self) -> None:
        config = MetricConfig(stop_speed_threshold=0.5, resume_speed_threshold=0.5)
        points = [
            tp(0.0, 0.0, 0.0, v=0.0),
            tp(1.0, 1.0, 0.0, v=1.0),
            tp(2.0, 1.5, 0.0, v=0.4),  # below 0.5: stopped under this config
            tp(3.0, 2.5, 0.0, v=1.0),
        ]
        result = make_result(EpisodeStatus.SUCCESS, points)
        assert compute_episode_metrics(result, metric_config=config).stop_and_go_count == 1
        assert compute_episode_metrics(result).stop_and_go_count == 0  # default band

    def test_config_rejects_inverted_hysteresis(self) -> None:
        with pytest.raises(ValueError):
            MetricConfig(stop_speed_threshold=0.2, resume_speed_threshold=0.1)


class TestNearMiss:
    def test_counts_points_below_threshold(self, mixed_grid: OccupancyGrid) -> None:
        # Box [2,3]x[2,3], radius 0.25: (2.5, 1.5) has clearance 0.25 (< 0.3
        # -> near miss); (0.5, 0.5) is far from the box but 0.25 from the map
        # edge... use a threshold small enough that only the first counts.
        config = MetricConfig(near_miss_clearance_threshold=0.26)
        points = [tp(0.0, 2.5, 1.5), tp(1.0, 2.5, 0.7)]  # clearances 0.25, 1.05
        metrics = compute_episode_metrics(
            make_result(EpisodeStatus.SUCCESS, points),
            grid=mixed_grid,
            robot_radius=0.25,
            metric_config=config,
        )
        assert metrics.near_miss_count == 1

    def test_penetrating_point_is_not_a_near_miss(self, mixed_grid: OccupancyGrid) -> None:
        # (2.5, 2.5) is inside the occupied box: negative clearance is the
        # collision, not a near miss — no double counting.
        metrics = compute_episode_metrics(
            make_result(EpisodeStatus.COLLISION, [tp(0.0, 2.5, 2.5)]),
            grid=mixed_grid,
            robot_radius=0.25,
        )
        assert metrics.near_miss_count == 0
        assert metrics.collision

    def test_none_without_grid(self) -> None:
        metrics = compute_episode_metrics(make_result(EpisodeStatus.SUCCESS, [tp(0.0, 2.5, 2.5)]))
        assert metrics.near_miss_count is None


class TestTimeToFirstCollision:
    def test_reports_first_collision_time(self) -> None:
        events = (EpisodeEvent(time=3.2, type="collision", message="hit wall"),)
        metrics = compute_episode_metrics(
            make_result(EpisodeStatus.COLLISION, [tp(0.0, 0.0, 0.0)], events=events)
        )
        assert metrics.time_to_first_collision == pytest.approx(3.2)

    def test_none_without_collision(self) -> None:
        events = (EpisodeEvent(time=9.9, type="success", message="arrived"),)
        metrics = compute_episode_metrics(
            make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)], events=events)
        )
        assert metrics.time_to_first_collision is None


class TestMetricConfigSnapshot:
    def test_default_config_recorded(self) -> None:
        metrics = compute_episode_metrics(make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)]))
        assert metrics.metric_config is not None
        assert metrics.metric_config.version == "1.0.0"

    def test_custom_config_recorded(self) -> None:
        config = MetricConfig(near_miss_clearance_threshold=0.5)
        metrics = compute_episode_metrics(
            make_result(EpisodeStatus.SUCCESS, [tp(0.0, 0.0, 0.0)]), metric_config=config
        )
        assert metrics.metric_config is not None
        assert metrics.metric_config.near_miss_clearance_threshold == 0.5


class TestBackwardCompatibility:
    def test_pre_f05_payload_deserializes_with_none_fields(self) -> None:
        # A metrics dict as stored before F05: no new field present.
        from planbench_metrics import EpisodeMetrics

        old_payload = {
            "status": "success",
            "success": True,
            "collision": False,
            "travel_time": 4.2,
            "steps": 42,
            "trajectory_length": 3.9,
            "average_speed": 0.93,
            "max_speed": 1.0,
            "smoothness": 0.12,
        }
        metrics = EpisodeMetrics.model_validate(old_payload)
        assert metrics.smoothness_squared is None
        assert metrics.local_planning_latency_p50 is None
        assert metrics.local_planning_latency_p95 is None
        assert metrics.local_planning_latency_p99 is None
        assert metrics.stop_and_go_count is None
        assert metrics.near_miss_count is None
        assert metrics.time_to_first_collision is None
        assert metrics.metric_config is None
