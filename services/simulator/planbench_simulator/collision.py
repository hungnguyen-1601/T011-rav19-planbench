"""Static collision checks and clearance for a circular robot.

Boundary-contact rule (project-wide, see docs/architecture.md): contact
counts as collision. The robot collides with an obstacle iff the
distance between their surfaces is at most EPS, i.e.
``clearance <= EPS``.

Clearance is the surface-to-surface distance: positive when separated,
non-positive on contact or penetration. The penetration magnitude is
exact for circle obstacles; for rectangles and grid cells it saturates
at ``-radius`` once the robot centre is inside the obstacle.

The region outside the map is treated as an obstacle: a robot circle
reaching the map boundary collides.

All functions are pure and deterministic.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from planbench_schemas.geometry import EPS, Point2D, distance_point_to_aabb
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle
from planbench_simulator.grid import OccupancyGrid


def _validate_radius(radius: float) -> None:
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError(f"radius must be a finite positive number, got {radius!r}")


def _map_bounds(grid: OccupancyGrid) -> tuple[float, float, float, float]:
    min_x = grid.origin.x
    min_y = grid.origin.y
    return (
        min_x,
        min_y,
        min_x + grid.width * grid.resolution,
        min_y + grid.height * grid.resolution,
    )


def _boundary_clearance(center: Point2D, grid: OccupancyGrid) -> float:
    """Signed distance from the centre to the region outside the map."""
    min_x, min_y, max_x, max_y = _map_bounds(grid)
    return min(center.x - min_x, max_x - center.x, center.y - min_y, max_y - center.y)


def clearance_to_circle(center: Point2D, radius: float, obstacle: CircleObstacle) -> float:
    """Surface-to-surface clearance between the robot and a circle."""
    _validate_radius(radius)
    distance = math.hypot(center.x - obstacle.center.x, center.y - obstacle.center.y)
    return distance - radius - obstacle.radius


def clearance_to_rectangle(center: Point2D, radius: float, obstacle: RectangleObstacle) -> float:
    """Surface-to-surface clearance between the robot and a rectangle."""
    _validate_radius(radius)
    distance = distance_point_to_aabb(
        center.x, center.y, obstacle.min_x, obstacle.min_y, obstacle.max_x, obstacle.max_y
    )
    return distance - radius


def clearance_to_obstacle(
    center: Point2D, radius: float, obstacle: CircleObstacle | RectangleObstacle
) -> float:
    """Clearance to a single static obstacle (dispatch by type)."""
    if isinstance(obstacle, CircleObstacle):
        return clearance_to_circle(center, radius, obstacle)
    if isinstance(obstacle, RectangleObstacle):
        return clearance_to_rectangle(center, radius, obstacle)
    raise TypeError(f"unsupported obstacle type: {type(obstacle).__name__}")


def collides_with_obstacle(
    center: Point2D, radius: float, obstacle: CircleObstacle | RectangleObstacle
) -> bool:
    """True iff the robot touches or penetrates the obstacle."""
    return clearance_to_obstacle(center, radius, obstacle) <= EPS


def collides_with_grid(center: Point2D, radius: float, grid: OccupancyGrid) -> bool:
    """True iff the robot circle touches a blocked cell or the map edge.

    Blocked cells are OCCUPIED cells, plus UNKNOWN cells when the grid
    was built with ``unknown_as_occupied=True``. Only cells inside the
    circle's bounding box are examined.
    """
    _validate_radius(radius)
    if _boundary_clearance(center, grid) - radius <= EPS:
        return True

    resolution = grid.resolution
    min_x, min_y, _, _ = _map_bounds(grid)
    row_lo = max(0, math.floor((center.y - radius - min_y) / resolution))
    row_hi = min(grid.height - 1, math.floor((center.y + radius - min_y) / resolution))
    col_lo = max(0, math.floor((center.x - radius - min_x) / resolution))
    col_hi = min(grid.width - 1, math.floor((center.x + radius - min_x) / resolution))
    for row in range(row_lo, row_hi + 1):
        for col in range(col_lo, col_hi + 1):
            if not grid.is_blocked_cell(row, col):
                continue
            cell_min_x = min_x + col * resolution
            cell_min_y = min_y + row * resolution
            distance = distance_point_to_aabb(
                center.x,
                center.y,
                cell_min_x,
                cell_min_y,
                cell_min_x + resolution,
                cell_min_y + resolution,
            )
            if distance - radius <= EPS:
                return True
    return False


def clearance_to_grid(center: Point2D, radius: float, grid: OccupancyGrid) -> float:
    """Clearance to the nearest blocked cell or to the map boundary.

    Scans every cell; intended for metrics and tests, not per-step hot
    loops (a cached distance field can be added when profiling demands
    it).
    """
    _validate_radius(radius)
    best = _boundary_clearance(center, grid)
    resolution = grid.resolution
    min_x, min_y, _, _ = _map_bounds(grid)
    for row in range(grid.height):
        for col in range(grid.width):
            if not grid.is_blocked_cell(row, col):
                continue
            cell_min_x = min_x + col * resolution
            cell_min_y = min_y + row * resolution
            distance = distance_point_to_aabb(
                center.x,
                center.y,
                cell_min_x,
                cell_min_y,
                cell_min_x + resolution,
                cell_min_y + resolution,
            )
            best = min(best, distance)
    return best - radius


#: How far a windowed clearance query looks before giving up and
#: reporting the window as a floor. Two metres is far outside anything
#: the safety metrics can distinguish: ``min_clearance`` is anchored at
#: two robot radii (~0.52 m for the reference robot), so every value past
#: that already scores a flat 1.0, and ``near_miss_rate`` counts against
#: ``clearance_warning_m``, smaller still.
DEFAULT_CLEARANCE_WINDOW_M = 2.0


def clearance_to_grid_within(
    center: Point2D,
    radius: float,
    grid: OccupancyGrid,
    window_m: float = DEFAULT_CLEARANCE_WINDOW_M,
) -> float:
    """Clearance to the grid, exact nearby and floored far away.

    :func:`clearance_to_grid` visits every cell, which is fine for a
    metric computed once and ruinous for HĐ-5's ``clearance_m`` — that is
    one query per recorded control step, and on a 40×25 m map at 5 cm it
    is 400 000 cell visits per row. An episode of 600 rows spends a
    quarter of a billion cell visits on a column whose useful range is
    half a metre.

    So this variant scans only the cells within ``window_m`` of the
    robot and reports ``window_m - radius`` when it finds nothing. The
    result is **exact wherever the value can change a metric** and a
    floor beyond that: both safety anchors saturate far below the window,
    so a robot two metres from anything scores identically whether the
    true distance is 2 m or 20 m.

    The floor is also the safe direction. Reporting *less* clearance than
    there is can only make a candidate look worse, never wave one
    through.
    """
    _validate_radius(radius)
    if window_m <= 0.0:
        raise ValueError(f"clearance window must be positive, got {window_m}")

    best = min(_boundary_clearance(center, grid), window_m)
    resolution = grid.resolution
    min_x, min_y, _, _ = _map_bounds(grid)
    row_lo = max(0, math.floor((center.y - window_m - min_y) / resolution))
    row_hi = min(grid.height - 1, math.floor((center.y + window_m - min_y) / resolution))
    col_lo = max(0, math.floor((center.x - window_m - min_x) / resolution))
    col_hi = min(grid.width - 1, math.floor((center.x + window_m - min_x) / resolution))
    for row in range(row_lo, row_hi + 1):
        cell_min_y = min_y + row * resolution
        for col in range(col_lo, col_hi + 1):
            if not grid.is_blocked_cell(row, col):
                continue
            cell_min_x = min_x + col * resolution
            distance = distance_point_to_aabb(
                center.x,
                center.y,
                cell_min_x,
                cell_min_y,
                cell_min_x + resolution,
                cell_min_y + resolution,
            )
            if distance < best:
                best = distance
    return best - radius


def clearance_to_obstacles(
    center: Point2D,
    radius: float,
    obstacles: Iterable[CircleObstacle | RectangleObstacle],
    grid: OccupancyGrid | None = None,
) -> float:
    """Minimum clearance over shape obstacles and, optionally, a grid.

    Returns ``math.inf`` for an empty obstacle list with no grid.
    """
    _validate_radius(radius)
    best = math.inf
    for obstacle in obstacles:
        best = min(best, clearance_to_obstacle(center, radius, obstacle))
    if grid is not None:
        best = min(best, clearance_to_grid(center, radius, grid))
    return best
