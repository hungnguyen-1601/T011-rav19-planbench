"""Per-episode metric computation from real trajectory data.

Metric definitions (documented contract):

- ``trajectory_length``: sum of Euclidean distances between consecutive
  trajectory points, metres.
- ``path_efficiency``: planned path length / actual trajectory length
  (only for successful episodes; ~1.0 means the robot tracked the
  planned path tightly; the planned path is the reference, so values
  can exceed 1 slightly if the robot cuts corners).
- ``smoothness``: sum of *squared* heading changes, Σ(Δθ_i)² (spec
  section 8.2, literal formula) — lower is smoother, 0 for a straight
  line. Deliberately **not** normalized by path length: this is the
  ground-truth metric definition, reported as-is. Because it is
  unnormalized, a longer path accumulates a larger value even if each
  turn is gentle — comparing it across episodes of very different
  length conflates "long" with "rough". Use ``smoothness_per_metre``
  (below) when that comparison is what's needed instead.
- ``smoothness_per_metre``: the same heading-change sum, but Σ|Δθ|
  (not squared) divided by trajectory length, rad/m — length-normalized
  so two episodes of different length stay comparable. This was
  PlanBench's original "smoothness" formula before it was split out;
  the leaderboard's overall_score still uses this one for exactly that
  reason (see apps/api/planbench_api/leaderboard.py).
- ``min_clearance`` / ``mean_clearance``: clearance (surface-to-surface
  distance, negative when penetrating) evaluated at every trajectory
  point against the grid and shape obstacles.
- ``average_speed``: trajectory length / travel time.
- ``local_planning_latency_p50/p95/p99``: percentiles of the local
  planner's per-step wall-clock latency (spec section 8.3 — p99 matters
  more than the mean here, because one slow step at 20 Hz control is
  enough time for the robot to run blind into something).
- ``stop_and_go_count``: number of times linear speed drops below a
  near-zero threshold and then rises back above it — a full stop
  followed by resuming motion (spec section 8.5), a signal of local
  planner oscillation rather than smooth, continuous travel.

All computations are deterministic and use only recorded episode data.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_metrics.statistics import percentile as _percentile_of
from planbench_schemas.episode import EpisodeResult, EpisodeStatus, TrajectoryPoint
from planbench_schemas.geometry import EPS, Point2D, normalize_angle
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle
from planbench_simulator.collision import clearance_to_obstacles
from planbench_simulator.grid import OccupancyGrid

#: Below this linear speed, the robot counts as "stopped" for
#: stop_and_go_count purposes — small enough to not trigger on ordinary
#: slow travel, large enough to absorb floating-point/simulation noise
#: around a commanded zero velocity.
STOPPED_SPEED_THRESHOLD = 0.02


class EpisodeMetrics(BaseModel):
    """Quantitative summary of one episode."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    status: EpisodeStatus
    success: bool
    collision: bool
    travel_time: float
    steps: int
    trajectory_length: float
    average_speed: float
    max_speed: float
    smoothness: float
    smoothness_per_metre: float
    planned_path_length: float | None = None
    path_efficiency: float | None = None
    min_clearance: float | None = None
    mean_clearance: float | None = None
    global_planning_time: float | None = None
    expanded_nodes: int | None = None
    mean_local_planning_latency: float | None = None
    max_local_planning_latency: float | None = None
    local_planning_latency_p50: float | None = None
    local_planning_latency_p95: float | None = None
    local_planning_latency_p99: float | None = None
    stop_and_go_count: int = 0


def compute_episode_metrics(
    result: EpisodeResult,
    *,
    planned_path_length: float | None = None,
    global_planning_time: float | None = None,
    expanded_nodes: int | None = None,
    grid: OccupancyGrid | None = None,
    obstacles: Sequence[CircleObstacle | RectangleObstacle] = (),
    robot_radius: float | None = None,
    local_planner_latencies: Sequence[float] = (),
) -> EpisodeMetrics:
    """Compute metrics from an episode result and optional plan context.

    Clearance metrics require both ``grid`` and ``robot_radius``.
    Latency values are wall-clock measurements: reported as metrics, but
    never part of the deterministic simulation contract.
    """
    trajectory = result.trajectory
    trajectory_length = sum(
        math.hypot(
            trajectory[i + 1].x - trajectory[i].x,
            trajectory[i + 1].y - trajectory[i].y,
        )
        for i in range(len(trajectory) - 1)
    )
    heading_changes = [
        normalize_angle(trajectory[i + 1].theta - trajectory[i].theta)
        for i in range(len(trajectory) - 1)
    ]
    smoothness = sum(delta * delta for delta in heading_changes)
    smoothness_per_metre = (
        sum(abs(delta) for delta in heading_changes) / trajectory_length
        if trajectory_length > EPS
        else 0.0
    )
    travel_time = result.elapsed_time
    average_speed = trajectory_length / travel_time if travel_time > EPS else 0.0
    max_speed = max((abs(p.linear_velocity) for p in trajectory), default=0.0)
    stop_and_go_count = _count_stop_and_go(trajectory)

    success = result.status is EpisodeStatus.SUCCESS
    path_efficiency: float | None = None
    if success and planned_path_length is not None and trajectory_length > EPS:
        path_efficiency = planned_path_length / trajectory_length

    min_clearance: float | None = None
    mean_clearance: float | None = None
    if grid is not None and robot_radius is not None and trajectory:
        clearances = [
            clearance_to_obstacles(Point2D(x=p.x, y=p.y), robot_radius, obstacles, grid)
            for p in trajectory
        ]
        finite = [c for c in clearances if math.isfinite(c)]
        if finite:
            min_clearance = min(finite)
            mean_clearance = sum(finite) / len(finite)

    return EpisodeMetrics(
        status=result.status,
        success=success,
        collision=result.status is EpisodeStatus.COLLISION,
        travel_time=travel_time,
        steps=result.steps,
        trajectory_length=trajectory_length,
        average_speed=average_speed,
        max_speed=max_speed,
        smoothness=smoothness,
        smoothness_per_metre=smoothness_per_metre,
        planned_path_length=planned_path_length,
        path_efficiency=path_efficiency,
        min_clearance=min_clearance,
        mean_clearance=mean_clearance,
        global_planning_time=global_planning_time,
        expanded_nodes=expanded_nodes,
        mean_local_planning_latency=(
            sum(local_planner_latencies) / len(local_planner_latencies)
            if local_planner_latencies
            else None
        ),
        max_local_planning_latency=(
            max(local_planner_latencies) if local_planner_latencies else None
        ),
        local_planning_latency_p50=(
            _percentile_of(local_planner_latencies, 50.0) if local_planner_latencies else None
        ),
        local_planning_latency_p95=(
            _percentile_of(local_planner_latencies, 95.0) if local_planner_latencies else None
        ),
        local_planning_latency_p99=(
            _percentile_of(local_planner_latencies, 99.0) if local_planner_latencies else None
        ),
        stop_and_go_count=stop_and_go_count,
    )


def _count_stop_and_go(trajectory: Sequence[TrajectoryPoint]) -> int:
    """Number of full stop-then-resume cycles *after* the robot has
    already been moving at least once.

    Every episode starts at rest (linear_velocity == 0), so a naive
    "stopped -> moving" edge count would count the ordinary start of
    the episode as a stop-and-go event, on every single episode. That
    is not what the spec metric means ("dừng hẳn rồi đi tiếp" — a stop
    *mid-journey*), so counting only starts once ``ever_moved`` has
    become true at least once.
    """
    count = 0
    ever_moved = False
    was_stopped = True
    for point in trajectory:
        is_stopped = abs(point.linear_velocity) < STOPPED_SPEED_THRESHOLD
        if not is_stopped:
            if was_stopped and ever_moved:
                count += 1
            ever_moved = True
        was_stopped = is_stopped
    return count
