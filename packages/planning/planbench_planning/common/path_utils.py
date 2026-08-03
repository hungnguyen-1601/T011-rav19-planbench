"""Path post-processing utilities: length, line of sight, simplification.

All functions are pure and deterministic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from planbench_schemas.geometry import Point2D, euclidean_distance
from planbench_simulator.grid import OccupancyGrid


def path_length(path: Sequence[Point2D]) -> float:
    """Total Euclidean length of a polyline, in metres."""
    return sum(euclidean_distance(path[i], path[i + 1]) for i in range(len(path) - 1))


def has_line_of_sight(
    grid: OccupancyGrid, a: Point2D, b: Point2D, step: float | None = None
) -> bool:
    """True iff the segment a-b crosses no blocked cell.

    Samples the segment every ``step`` metres (default: resolution / 4).
    Points outside the map count as blocked. On an inflated grid this
    approximates a swept-circle check for the robot.
    """
    if step is None:
        step = grid.resolution / 4.0
    if step <= 0:
        raise ValueError(f"step must be positive, got {step!r}")
    distance = euclidean_distance(a, b)
    samples = max(1, math.ceil(distance / step))
    for i in range(samples + 1):
        t = i / samples
        x = a.x + (b.x - a.x) * t
        y = a.y + (b.y - a.y) * t
        if grid.is_occupied(x, y):
            return False
    return True


def simplify_path(
    grid: OccupancyGrid, path: Sequence[Point2D], step: float | None = None
) -> tuple[Point2D, ...]:
    """Greedy line-of-sight shortcutting; keeps both endpoints.

    From each anchor, jumps to the farthest waypoint still visible.
    The result never crosses cells the original path avoided (validated
    by the same line-of-sight sampling used for planning).
    """
    if len(path) <= 2:
        return tuple(path)
    result: list[Point2D] = [path[0]]
    anchor = 0
    last = len(path) - 1
    while anchor < last:
        next_index = anchor + 1
        for j in range(last, anchor, -1):
            if has_line_of_sight(grid, path[anchor], path[j], step):
                next_index = j
                break
        result.append(path[next_index])
        anchor = next_index
    return tuple(result)
