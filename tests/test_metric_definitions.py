"""Metric definitions and the reference path (CONTRACTS HĐ-6).

Every test here builds a trace by hand and asks what the contract asks:
can this number be recomputed from the file plus the profile, and does it
come out the way HĐ-6 defines it. The refusals matter as much as the
values — a metric computed against the wrong mission, or judged by a
tolerance the deployment never declared, is a plausible-looking number
produced under rules nobody stated.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from task_profile_fakes import make_profile

from planbench_decision.candidate import ArtifactResourceProfile, StructuralResourceProfile
from planbench_metrics.definitions import (
    EpisodeMetricSet,
    MetricError,
    compute_metrics,
    memory_estimate_mb,
)
from planbench_metrics.reference_path import (
    ReferencePathError,
    clear_reference_cache,
    reference_path_length,
)
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.robot import RobotState
from planbench_simulator.trace import EpisodeTraceRecorder, read_trace

STRUCTURAL = StructuralResourceProfile(
    kind="structural",
    target_implementation="cpp_ros2",
    bytes_per_search_node=40,
    bytes_per_tree_node=40,
    bytes_per_costmap_cell=1,
    costmap_layers=3,
    fixed_overhead_mb=8.0,
)


@pytest.fixture(autouse=True)
def _clean_reference_cache():
    clear_reference_cache()
    yield
    clear_reference_cache()


def empty_map(width: int = 40, height: int = 40, resolution: float = 0.25) -> MapData:
    """A 10 x 10 m room with no obstacles, at 0.25 m."""
    return MapData(
        name="room",
        width=width,
        height=height,
        resolution=resolution,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=(CellState.FREE.value,) * (width * height),
    )


def walled_map() -> MapData:
    """The same room, split by a wall with a 1 m doorway at y in [4, 5]."""
    width = height = 40
    cells = [CellState.FREE.value] * (width * height)
    for row in range(height):
        if not (16 <= row < 20):
            cells[row * width + 20] = CellState.OCCUPIED.value
    return MapData(
        name="room_with_door",
        width=width,
        height=height,
        resolution=0.25,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(cells),
    )


def profile_with_mission(start: tuple[float, float], goal: tuple[float, float], **overrides):
    missions = [
        {
            "id": "m1",
            "start": [start[0], start[1], 0.0],
            "goal": [goal[0], goal[1], 0.0],
            "probability": 1.0,
        }
    ]
    return make_profile(missions=missions, **overrides)


def context(mission_id: str = "m1", seed: int = 1) -> EpisodeContext:
    return EpisodeContext(task_profile_id="warehouse_a_v1", mission_id=mission_id, seed=seed)


def write_trace(
    tmp_path: Path,
    samples: list[tuple[float, float, float, float, float, str | None]],
    *,
    ctx: EpisodeContext | None = None,
    clearance: float = 1.0,
    latency_ms: float = 5.0,
    peak_search_nodes: int = 0,
    costmap_cells: int = 0,
):
    """Write a trace from ``(t, x, y, theta, v, event)`` rows."""
    ctx = ctx or context()
    recorder = EpisodeTraceRecorder(
        ctx, "cand12345678", clearance=lambda _: clearance, root=tmp_path
    )
    for t, x, y, theta, v, event in samples:
        recorder.record(
            t,
            RobotState(pose=Pose2D(x=x, y=y, theta=theta), linear_velocity=v),
            event,
            planner_latency_ms=latency_ms,
        )
    return read_trace(
        recorder.close(peak_search_nodes=peak_search_nodes, costmap_cells=costmap_cells)
    )


def straight_run(
    tmp_path: Path, *, distance: float = 4.0, duration: float = 10.0, **kwargs
) -> tuple:
    """A successful straight drive from (1, 1) to (1 + distance, 1)."""
    steps = 8
    samples = []
    for i in range(steps + 1):
        fraction = i / steps
        event = "goal_reached" if i == steps else None
        samples.append(
            (
                duration * fraction,
                1.0 + distance * fraction,
                1.0,
                0.0,
                0.0 if i in (0, steps) else 1.0,
                event,
            )
        )
    return write_trace(tmp_path, samples, **kwargs)


class TestReferencePath:
    def test_open_room_reference_is_the_straight_line(self) -> None:
        """Nothing in the way: the reference is the Euclidean distance,
        not the staircase an 8-connected grid would walk."""
        length = reference_path_length(empty_map(), Point2D(x=1.0, y=1.0), Point2D(x=8.0, y=5.0))
        assert length == pytest.approx(math.dist((1.0, 1.0), (8.0, 5.0)), rel=0.02)

    def test_detour_through_a_doorway_is_longer_than_the_straight_line(self) -> None:
        straight = math.dist((1.0, 1.0), (9.0, 1.0))
        length = reference_path_length(walled_map(), Point2D(x=1.0, y=1.0), Point2D(x=9.0, y=1.0))
        assert length is not None
        assert length > straight

    def test_unreachable_goal_returns_none(self) -> None:
        """A fact about the profile, not about any candidate."""
        width = height = 40
        cells = [CellState.FREE.value] * (width * height)
        for row in range(height):
            cells[row * width + 20] = CellState.OCCUPIED.value
        sealed = MapData(
            name="sealed",
            width=width,
            height=height,
            resolution=0.25,
            origin=Pose2D(x=0.0, y=0.0, theta=0.0),
            cells=tuple(cells),
        )
        assert reference_path_length(sealed, Point2D(x=1.0, y=1.0), Point2D(x=9.0, y=1.0)) is None

    def test_pose_outside_the_map_is_refused(self) -> None:
        with pytest.raises(ReferencePathError, match="outside map"):
            reference_path_length(empty_map(), Point2D(x=1.0, y=1.0), Point2D(x=99.0, y=1.0))

    def test_blocked_endpoint_is_refused(self) -> None:
        with pytest.raises(ReferencePathError, match="blocked cell"):
            reference_path_length(walled_map(), Point2D(x=5.0, y=1.0), Point2D(x=9.0, y=1.0))

    def test_result_is_cached_per_context(self) -> None:
        first = reference_path_length(empty_map(), Point2D(x=1.0, y=1.0), Point2D(x=8.0, y=5.0))
        second = reference_path_length(empty_map(), Point2D(x=1.0, y=1.0), Point2D(x=8.0, y=5.0))
        assert first == second


class TestEfficiency:
    def test_perfect_run_scores_one(self, tmp_path: Path) -> None:
        """The robot drove the reference path: efficiency 1.0, and the
        HĐ-15.1 bound L_ref <= path_length holds with equality."""
        trace = straight_run(tmp_path, distance=4.0)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.path_length_m == pytest.approx(4.0)
        assert metrics.l_ref_m == pytest.approx(4.0, rel=0.02)
        assert metrics.path_efficiency == pytest.approx(1.0, rel=0.02)
        assert metrics.l_ref_m <= metrics.path_length_m + 1e-9

    def test_wandering_run_scores_below_one(self, tmp_path: Path) -> None:
        samples = [
            (0.0, 1.0, 1.0, 0.0, 0.0, None),
            (1.0, 1.0, 3.0, 0.0, 1.0, None),
            (2.0, 5.0, 3.0, 0.0, 1.0, None),
            (3.0, 5.0, 1.0, 0.0, 0.0, "goal_reached"),
        ]
        trace = write_trace(tmp_path, samples)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.path_length_m == pytest.approx(8.0)
        assert metrics.path_efficiency == pytest.approx(0.5, rel=0.05)

    def test_time_efficiency_uses_v_max_from_the_profile(self, tmp_path: Path) -> None:
        """T_ideal = L_ref / v_max, and v_max is the deployment's, never
        a constant in the metrics module (HĐ-7)."""
        trace = straight_run(tmp_path, distance=4.0, duration=10.0)
        profile = profile_with_mission((1.0, 1.0), (5.0, 1.0))
        metrics = compute_metrics(trace, profile, context(), empty_map())
        assert metrics.t_ideal_s == pytest.approx(metrics.l_ref_m / 0.8, rel=1e-6)
        assert metrics.travel_time_s == pytest.approx(10.0)
        assert metrics.time_efficiency == pytest.approx(metrics.t_ideal_s / 10.0, rel=1e-6)

    def test_a_robot_that_never_moved_scores_zero_not_infinity(self, tmp_path: Path) -> None:
        samples = [(0.0, 1.0, 1.0, 0.0, 0.0, None), (1.0, 1.0, 1.0, 0.0, 0.0, "timeout")]
        trace = write_trace(tmp_path, samples)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.path_length_m == 0.0
        assert metrics.path_efficiency == 0.0


class TestSuccessAndFailure:
    def test_success_needs_goal_no_collision_no_timeout(self, tmp_path: Path) -> None:
        trace = straight_run(tmp_path)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.success is True
        assert metrics.failure_reason is None

    def test_collision_beats_a_later_timeout(self, tmp_path: Path) -> None:
        """ "It crashed, then ran out of time" is a crash."""
        samples = [
            (0.0, 1.0, 1.0, 0.0, 0.0, None),
            (1.0, 2.0, 1.0, 0.0, 1.0, "collision"),
            (2.0, 2.0, 1.0, 0.0, 0.0, "timeout"),
        ]
        trace = write_trace(tmp_path, samples)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.success is False
        assert metrics.collision_count == 1
        assert metrics.failure_reason == "collision"

    def test_goal_reached_with_a_collision_is_not_a_success(self, tmp_path: Path) -> None:
        samples = [
            (0.0, 1.0, 1.0, 0.0, 0.0, None),
            (1.0, 3.0, 1.0, 0.0, 1.0, "collision"),
            (2.0, 5.0, 1.0, 0.0, 0.0, "goal_reached"),
        ]
        trace = write_trace(tmp_path, samples)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.success is False
        assert metrics.failure_reason == "collision"

    def test_claiming_the_goal_from_2_m_away_is_refused(self, tmp_path: Path) -> None:
        """A trace that claims the goal while ending 2 m away was judged
        against a tolerance the deployment never declared (HĐ-7)."""
        samples = [
            (0.0, 1.0, 1.0, 0.0, 0.0, None),
            (1.0, 3.0, 1.0, 0.0, 1.0, "goal_reached"),
        ]
        trace = write_trace(tmp_path, samples)
        with pytest.raises(MetricError, match="different tolerance"):
            compute_metrics(
                trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
            )

    def test_heading_outside_tolerance_is_not_the_goal(self, tmp_path: Path) -> None:
        """``goal_tolerance_rad`` is part of the definition too, so a
        robot parked at the right place facing backwards has not
        arrived — and claiming it is refused."""
        samples = [
            (0.0, 1.0, 1.0, 0.0, 0.0, None),
            (1.0, 5.0, 1.0, math.pi, 0.0, "goal_reached"),
        ]
        trace = write_trace(tmp_path, samples)
        with pytest.raises(MetricError, match="outside the profile's tolerance"):
            compute_metrics(
                trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
            )

    def test_standing_near_the_goal_at_timeout_is_not_arrival(self, tmp_path: Path) -> None:
        """The run's verdict stands: drifting within tolerance of the
        goal is not the same as reaching it."""
        samples = [
            (0.0, 1.0, 1.0, 0.0, 0.0, None),
            (1.0, 5.0, 1.0, 0.0, 0.0, "timeout"),
        ]
        trace = write_trace(tmp_path, samples)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.success is False
        assert metrics.failure_reason == "timeout"


class TestSafetyAndDiagnostics:
    def test_near_miss_rate_is_per_metre_and_uses_the_declared_threshold(
        self, tmp_path: Path
    ) -> None:
        trace = straight_run(tmp_path, distance=4.0, clearance=0.30)
        profile = profile_with_mission((1.0, 1.0), (5.0, 1.0))
        metrics = compute_metrics(trace, profile, context(), empty_map())
        # clearance 0.30 < clearance_warning_m 0.35 on all 9 samples
        assert metrics.min_clearance == pytest.approx(0.30)
        assert metrics.near_miss_rate == pytest.approx(9 / 4.0)

    def test_clearance_above_the_threshold_is_not_a_near_miss(self, tmp_path: Path) -> None:
        trace = straight_run(tmp_path, clearance=1.0)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.near_miss_rate == 0.0

    def test_smoothness_survives_the_angle_wrap(self, tmp_path: Path) -> None:
        """Crossing ±pi while driving straight must not read as ~39 rad²
        of roughness."""
        samples = [
            (0.0, 1.0, 1.0, math.pi - 0.01, 0.0, None),
            (1.0, 3.0, 1.0, -math.pi + 0.01, 1.0, None),
            (2.0, 5.0, 1.0, -math.pi + 0.01, 0.0, None),
        ]
        trace = write_trace(tmp_path, samples)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.smoothness == pytest.approx(0.02**2, abs=1e-6)

    def test_stop_and_go_ignores_the_initial_standstill(self, tmp_path: Path) -> None:
        samples = [
            (0.0, 1.0, 1.0, 0.0, 0.0, None),  # start at rest: not a stop
            (1.0, 2.0, 1.0, 0.0, 1.0, None),
            (2.0, 2.0, 1.0, 0.0, 0.0, None),  # stop
            (3.0, 3.0, 1.0, 0.0, 1.0, None),  # go again -> 1
            (4.0, 3.0, 1.0, 0.0, 0.0, None),  # stop
            (5.0, 4.0, 1.0, 0.0, 1.0, None),  # go again -> 2, ends short of the goal
        ]
        trace = write_trace(tmp_path, samples)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.stop_and_go_count == 2

    def test_p99_latency_comes_from_the_trace_column(self, tmp_path: Path) -> None:
        trace = straight_run(tmp_path, latency_ms=23.0)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.p99_latency_ms == pytest.approx(23.0)


class TestMemoryEstimate:
    def test_structural_follows_the_contract_formula(self) -> None:
        """HĐ-7.3, worked by hand: 400 000 cells x 1 byte x 3 layers is
        ~1.14 MB, 100 000 search nodes x 40 B is ~3.81 MB, plus 8 MB
        fixed."""
        estimate = memory_estimate_mb(
            STRUCTURAL, peak_search_nodes=100_000, peak_tree_nodes=0, costmap_cells=400_000
        )
        expected = (100_000 * 40 + 400_000 * 1 * 3) / (1024 * 1024) + 8.0
        assert estimate == pytest.approx(expected)

    def test_artifact_is_weights_plus_runtime(self) -> None:
        profile = ArtifactResourceProfile(
            kind="artifact", model_artifact_mb=340.0, runtime_footprint_mb=2100.0
        )
        assert memory_estimate_mb(profile, peak_search_nodes=999_999) == pytest.approx(2440.0)

    def test_estimate_ignores_peak_rss(self, tmp_path: Path) -> None:
        """§17 ban 13: the Python process's RSS never becomes the number
        G5 judges."""
        trace = straight_run(tmp_path, peak_search_nodes=1000, costmap_cells=1600)
        metrics = compute_metrics(
            trace,
            profile_with_mission((1.0, 1.0), (5.0, 1.0)),
            context(),
            empty_map(),
            resource_profile=STRUCTURAL,
        )
        assert metrics.memory_estimate_mb is not None
        assert metrics.peak_rss_mb > 0.0
        assert metrics.memory_estimate_mb != metrics.peak_rss_mb
        assert metrics.memory_estimate_mb == pytest.approx(
            memory_estimate_mb(STRUCTURAL, peak_search_nodes=1000, costmap_cells=1600)
        )

    def test_absent_resource_profile_yields_none_not_zero(self, tmp_path: Path) -> None:
        """Zero would read as "fits in any budget"; None says G5 has
        nothing to judge."""
        trace = straight_run(tmp_path)
        metrics = compute_metrics(
            trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), context(), empty_map()
        )
        assert metrics.memory_estimate_mb is None


class TestRefusals:
    def test_trace_scored_against_another_context(self, tmp_path: Path) -> None:
        """The metrics would describe one episode using another episode's
        mission and seed."""
        trace = straight_run(tmp_path)
        other = context(seed=99)
        with pytest.raises(MetricError, match="is being scored against"):
            compute_metrics(trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), other, empty_map())

    def test_profile_without_that_mission(self, tmp_path: Path) -> None:
        ctx = context(mission_id="m_other")
        trace = straight_run(tmp_path, ctx=ctx)
        with pytest.raises(MetricError, match="has no mission"):
            compute_metrics(trace, profile_with_mission((1.0, 1.0), (5.0, 1.0)), ctx, empty_map())

    def test_mission_with_no_route_is_refused(self, tmp_path: Path) -> None:
        """No ratio is quoted against a path that does not exist."""
        width = height = 40
        cells = [CellState.FREE.value] * (width * height)
        for row in range(height):
            cells[row * width + 20] = CellState.OCCUPIED.value
        sealed = MapData(
            name="sealed",
            width=width,
            height=height,
            resolution=0.25,
            origin=Pose2D(x=0.0, y=0.0, theta=0.0),
            cells=tuple(cells),
        )
        samples = [(0.0, 1.0, 1.0, 0.0, 0.0, None), (1.0, 1.0, 2.0, 0.0, 1.0, "no_path")]
        trace = write_trace(tmp_path, samples)
        with pytest.raises(MetricError, match="no route"):
            compute_metrics(trace, profile_with_mission((1.0, 1.0), (9.0, 1.0)), context(), sealed)

    def test_metric_set_refuses_unknown_fields(self) -> None:
        """A metric defined anywhere but this module is a DoD violation
        for every later PR (HĐ-15.3)."""
        with pytest.raises(ValueError):
            EpisodeMetricSet(
                episode_context_id="a",
                candidate_id="b",
                success=True,
                failure_reason=None,
                collision_count=0,
                min_clearance=1.0,
                near_miss_rate=0.0,
                path_length_m=1.0,
                travel_time_s=1.0,
                l_ref_m=1.0,
                path_efficiency=1.0,
                t_ideal_s=1.0,
                time_efficiency=1.0,
                smoothness=0.0,
                stop_and_go_count=0,
                p99_latency_ms=1.0,
                peak_search_nodes=0,
                peak_tree_nodes=0,
                costmap_cells=0,
                peak_rss_mb=1.0,
                cpu_time_per_mission_s=1.0,
                jerk=0.4,  # type: ignore[call-arg]
            )
