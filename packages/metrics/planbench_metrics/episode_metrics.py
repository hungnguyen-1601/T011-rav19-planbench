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
- ``min_clearance`` / ``mean_clearance``: clearance (surface-to-surface
  distance, negative when penetrating) evaluated at every trajectory
  point against the grid and shape obstacles.
- ``average_speed``: trajectory length / travel time.

All computations are deterministic and use only recorded episode data.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_schemas.episode import EpisodeResult, EpisodeStatus
from planbench_schemas.geometry import EPS, Point2D, normalize_angle
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle
from planbench_simulator.collision import clearance_to_obstacles
from planbench_simulator.grid import OccupancyGrid


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
    planned_path_length: float | None = None
    path_efficiency: float | None = None
    min_clearance: float | None = None
    mean_clearance: float | None = None
    global_planning_time: float | None = None
    expanded_nodes: int | None = None
    mean_local_planning_latency: float | None = None
    max_local_planning_latency: float | None = None


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
    heading_change = sum(
        abs(normalize_angle(trajectory[i + 1].theta - trajectory[i].theta))
        for i in range(len(trajectory) - 1)
    )
    smoothness = heading_change / trajectory_length if trajectory_length > EPS else 0.0
    travel_time = result.elapsed_time
    average_speed = trajectory_length / travel_time if travel_time > EPS else 0.0
    max_speed = max((abs(p.linear_velocity) for p in trajectory), default=0.0)

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
    )
