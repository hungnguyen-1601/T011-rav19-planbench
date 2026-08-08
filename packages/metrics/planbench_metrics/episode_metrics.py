"""Per-episode metric computation from real trajectory data.

Metric definitions (documented contract):

- ``trajectory_length``: sum of Euclidean distances between consecutive
  trajectory points, metres.
- ``path_efficiency``: planned path length / actual trajectory length
  (only for successful episodes; ~1.0 means the robot tracked the
  planned path tightly; the planned path is the reference, so values
  can exceed 1 slightly if the robot cuts corners).
- ``smoothness``: sum of absolute heading changes divided by trajectory
  length, rad/m. Lower is smoother; 0 for a straight line.
  DEPRECATED NAME: this is a *heading-change rate*, not the smoothness
  the spec (section 8.2) defines. Kept because stored reports and
  existing clients read it; quote ``smoothness_squared`` instead.
- ``smoothness_squared``: the spec's smoothness, ``S = sum((dtheta_i)^2)``
  over consecutive heading changes, rad^2. Lower is smoother; 0 for a
  straight line. Unlike the rate above it is not normalised by length,
  so it is only comparable between trajectories on the same scenario.
- ``min_clearance`` / ``mean_clearance``: clearance (surface-to-surface
  distance, negative when penetrating) evaluated at every trajectory
  point against the grid and shape obstacles.
- ``average_speed``: trajectory length / travel time.
- ``local_planning_latency_p50/p95/p99``: percentiles of the per-step
  local-planner latencies. The mean hides exactly the risk that matters
  (spec section 8.3): a controller that is fast on average but freezes
  for 200 ms once per hundred steps is a controller that drives blind.
- ``stop_and_go_count``: number of times the robot, having been moving,
  dropped below the stop threshold and later resumed. The initial
  standstill is never counted (``ever_moved`` guard), and the two
  thresholds form a hysteresis band so speed jitter around a single
  threshold is not counted as repeated stops.
- ``near_miss_count``: trajectory points whose clearance is positive but
  below the warning threshold. Penetrating points (clearance <= 0) are
  the collision, already reported separately — counting them here would
  double-count one event as two.
- ``time_to_first_collision``: simulation time of the first recorded
  collision event; None when the episode had no collision.
- ``replan_count``: how many extra global paths the stack requested,
  counted by the stack as it runs rather than derived afterwards — a
  replan leaves no signature in the trajectory to recover it from.

When an episode replanned, two fields change meaning and the docstrings
above are read with this caveat: ``global_planning_time`` and
``expanded_nodes`` are totals over every plan the episode used, and
``planned_path_length`` (hence ``path_efficiency``) describes the last
path only, the one the robot was following at the end. Comparing
``path_efficiency`` between a run that replanned and one that did not
therefore compares against two different references — the replanning
config is part of the benchmark conditions precisely so that within one
comparison it is the same for everybody.

Thresholds live in :class:`MetricConfig`, which is versioned and
snapshotted into every :class:`EpisodeMetrics` (``metric_config``): a
count without its threshold is not reproducible, and a threshold change
must never silently relabel numbers computed under the old one.

All computations are deterministic and use only recorded episode data.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from planbench_schemas.episode import (
    EpisodeEvent,
    EpisodeResult,
    EpisodeStatus,
    TrajectoryPoint,
)
from planbench_schemas.geometry import EPS, Point2D, normalize_angle
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle
from planbench_simulator.collision import clearance_to_obstacles
from planbench_simulator.grid import OccupancyGrid

METRIC_CONFIG_VERSION = "1.0.0"


class MetricConfig(BaseModel):
    """Versioned thresholds for derived episode metrics (F05).

    The version changes whenever a default threshold changes, so two
    reports can be told apart by the rules they were computed under.
    Thresholds are deliberately not per-algorithm: a stop counted for
    DWA must be a stop for every other stack too.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    version: str = METRIC_CONFIG_VERSION
    #: Below this speed (m/s) a moving robot is considered stopped.
    stop_speed_threshold: float = 0.05
    #: Above this speed (m/s) a stopped robot is considered moving again.
    #: Must not be below the stop threshold — the gap is the hysteresis
    #: band that keeps jitter around one value from counting as many
    #: stop-and-go cycles.
    resume_speed_threshold: float = 0.10
    #: Clearance (m) under which a trajectory point counts as a near miss.
    near_miss_clearance_threshold: float = 0.30

    @model_validator(mode="after")
    def _validate(self) -> MetricConfig:
        if self.stop_speed_threshold < 0 or self.near_miss_clearance_threshold < 0:
            raise ValueError("thresholds must be non-negative")
        if self.resume_speed_threshold < self.stop_speed_threshold:
            raise ValueError(
                "resume_speed_threshold must be >= stop_speed_threshold "
                "(the hysteresis band cannot be negative)"
            )
        return self


DEFAULT_METRIC_CONFIG = MetricConfig()


class EpisodeMetrics(BaseModel):
    """Quantitative summary of one episode.

    Every field added by F05 defaults to None so metrics stored before
    it deserialize unchanged; None always means "not computed", never
    zero.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    status: EpisodeStatus
    success: bool
    collision: bool
    travel_time: float
    steps: int
    trajectory_length: float
    average_speed: float
    max_speed: float
    #: Deprecated heading-change rate (rad/m); see module docstring.
    smoothness: float
    planned_path_length: float | None = None
    path_efficiency: float | None = None
    min_clearance: float | None = None
    mean_clearance: float | None = None
    global_planning_time: float | None = None
    expanded_nodes: int | None = None
    mean_local_planning_latency: float | None = None
    max_local_planning_latency: float | None = None
    #: Spec smoothness ``S = sum((dtheta)^2)`` (rad^2), F05.
    smoothness_squared: float | None = None
    local_planning_latency_p50: float | None = None
    local_planning_latency_p95: float | None = None
    local_planning_latency_p99: float | None = None
    stop_and_go_count: int | None = None
    #: None when clearance could not be evaluated (no grid / no radius).
    near_miss_count: int | None = None
    time_to_first_collision: float | None = None
    #: Snapshot of the thresholds these metrics were computed under.
    metric_config: MetricConfig | None = None
    #: How many times the stack asked for a new global path. 0 for every
    #: run with replanning disabled, which is every run before the
    #: feature existed; None only for metrics stored before the field
    #: existed, where "not recorded" is the honest answer.
    replan_count: int | None = None


def _percentiles(values: Sequence[float]) -> tuple[float, float, float] | None:
    """``(p50, p95, p99)`` with linear interpolation, or None when empty."""
    if not values:
        return None
    p50, p95, p99 = np.percentile(np.asarray(values, dtype=float), [50, 95, 99])
    return (float(p50), float(p95), float(p99))


def _stop_and_go_count(trajectory: Sequence[TrajectoryPoint], config: MetricConfig) -> int:
    """Count moving -> stopped -> moving cycles with hysteresis.

    The robot must first exceed the resume threshold (``ever_moved``)
    before any stop can be counted, so the standstill at episode start
    is not a stop-and-go event.
    """
    count = 0
    ever_moved = False
    stopped = False
    for point in trajectory:
        speed = abs(point.linear_velocity)
        if not ever_moved:
            ever_moved = speed > config.resume_speed_threshold
            continue
        if stopped:
            if speed > config.resume_speed_threshold:
                stopped = False
                count += 1
        elif speed < config.stop_speed_threshold:
            stopped = True
    return count


def _time_to_first_collision(events: Sequence[EpisodeEvent]) -> float | None:
    times = [event.time for event in events if event.type == EpisodeStatus.COLLISION.value]
    return min(times) if times else None


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
    metric_config: MetricConfig | None = None,
    replan_count: int | None = None,
) -> EpisodeMetrics:
    """Compute metrics from an episode result and optional plan context.

    Clearance metrics require both ``grid`` and ``robot_radius``.
    Latency values are wall-clock measurements: reported as metrics, but
    never part of the deterministic simulation contract.
    ``metric_config`` defaults to :data:`DEFAULT_METRIC_CONFIG` and is
    snapshotted into the result.
    """
    config = metric_config or DEFAULT_METRIC_CONFIG
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
    heading_change = sum(abs(delta) for delta in heading_changes)
    smoothness = heading_change / trajectory_length if trajectory_length > EPS else 0.0
    smoothness_squared = sum(delta**2 for delta in heading_changes)
    travel_time = result.elapsed_time
    average_speed = trajectory_length / travel_time if travel_time > EPS else 0.0
    max_speed = max((abs(p.linear_velocity) for p in trajectory), default=0.0)

    success = result.status is EpisodeStatus.SUCCESS
    path_efficiency: float | None = None
    if success and planned_path_length is not None and trajectory_length > EPS:
        path_efficiency = planned_path_length / trajectory_length

    min_clearance: float | None = None
    mean_clearance: float | None = None
    near_miss_count: int | None = None
    if grid is not None and robot_radius is not None and trajectory:
        clearances = [
            clearance_to_obstacles(Point2D(x=p.x, y=p.y), robot_radius, obstacles, grid)
            for p in trajectory
        ]
        finite = [c for c in clearances if math.isfinite(c)]
        if finite:
            min_clearance = min(finite)
            mean_clearance = sum(finite) / len(finite)
        near_miss_count = sum(1 for c in finite if 0.0 < c < config.near_miss_clearance_threshold)

    latency_percentiles = _percentiles(local_planner_latencies)

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
        smoothness_squared=smoothness_squared,
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
        local_planning_latency_p50=latency_percentiles[0] if latency_percentiles else None,
        local_planning_latency_p95=latency_percentiles[1] if latency_percentiles else None,
        local_planning_latency_p99=latency_percentiles[2] if latency_percentiles else None,
        stop_and_go_count=_stop_and_go_count(trajectory, config),
        near_miss_count=near_miss_count,
        time_to_first_collision=_time_to_first_collision(result.events),
        metric_config=config,
        replan_count=replan_count,
    )
