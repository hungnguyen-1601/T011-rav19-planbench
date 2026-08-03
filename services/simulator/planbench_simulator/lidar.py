"""Simulated planar LiDAR via grid ray casting (Amanatides–Woo DDA).

Conventions:
- A ray stops at the entry face of the first blocked cell (OCCUPIED, or
  UNKNOWN when the grid treats unknown as occupied) and returns that
  distance, clamped to ``max_range``.
- A ray that leaves the map without hitting a blocked cell returns
  ``max_range`` (the void beyond the map reflects nothing; maps should
  model physical walls explicitly).
- A sensor origin inside a blocked cell returns 0.0 for every ray.

Deterministic: no randomness, no noise model (a seeded noise model can
be layered on later without changing this module).
"""

from __future__ import annotations

import math

from planbench_schemas.geometry import Pose2D
from planbench_schemas.sensor import LidarConfig
from planbench_simulator.grid import OccupancyGrid


def cast_ray(grid: OccupancyGrid, x: float, y: float, angle: float, max_range: float) -> float:
    """Distance from (x, y) along ``angle`` to the first blocked cell.

    Raises:
        ValueError: If the origin lies outside the map or ``max_range``
            is not a finite positive number.
    """
    if not math.isfinite(max_range) or max_range <= 0:
        raise ValueError(f"max_range must be a finite positive number, got {max_range!r}")
    start_cell = grid.world_to_grid(x, y)
    if start_cell is None:
        raise ValueError(f"ray origin ({x}, {y}) is outside the map")
    row, col = start_cell
    if grid.is_blocked_cell(row, col):
        return 0.0

    direction_x = math.cos(angle)
    direction_y = math.sin(angle)
    resolution = grid.resolution
    origin_x, origin_y = grid.origin.x, grid.origin.y

    step_col = 1 if direction_x > 0 else -1 if direction_x < 0 else 0
    step_row = 1 if direction_y > 0 else -1 if direction_y < 0 else 0

    if direction_x > 0:
        t_max_x = (origin_x + (col + 1) * resolution - x) / direction_x
        t_delta_x = resolution / direction_x
    elif direction_x < 0:
        t_max_x = (origin_x + col * resolution - x) / direction_x
        t_delta_x = resolution / -direction_x
    else:
        t_max_x = math.inf
        t_delta_x = math.inf

    if direction_y > 0:
        t_max_y = (origin_y + (row + 1) * resolution - y) / direction_y
        t_delta_y = resolution / direction_y
    elif direction_y < 0:
        t_max_y = (origin_y + row * resolution - y) / direction_y
        t_delta_y = resolution / -direction_y
    else:
        t_max_y = math.inf
        t_delta_y = math.inf

    while True:
        if t_max_x <= t_max_y:
            t_hit = t_max_x
            t_max_x += t_delta_x
            col += step_col
        else:
            t_hit = t_max_y
            t_max_y += t_delta_y
            row += step_row
        if t_hit > max_range:
            return max_range
        if not (0 <= row < grid.height and 0 <= col < grid.width):
            return max_range
        if grid.is_blocked_cell(row, col):
            return min(t_hit, max_range)


def scan(grid: OccupancyGrid, pose: Pose2D, config: LidarConfig) -> tuple[float, ...]:
    """Full LiDAR scan at ``pose``; ray i at relative angle
    ``-span/2 + i * span / num_rays`` from the heading."""
    increment = config.angle_span / config.num_rays
    start = pose.theta - config.angle_span / 2.0
    return tuple(
        cast_ray(grid, pose.x, pose.y, start + i * increment, config.max_range)
        for i in range(config.num_rays)
    )
