"""Occupancy grid queries and obstacle inflation.

Wraps an immutable :class:`planbench_schemas.map.MapData`. All
operations are pure (no mutation, no global state) and deterministic.

Safety conventions (see docs/architecture.md):
- World coordinates outside the map are reported as occupied.
- UNKNOWN cells count as occupied when ``unknown_as_occupied`` is True
  (the default).
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from planbench_schemas.geometry import EPS, Point2D, distance_point_to_aabb
from planbench_schemas.map import CellState, MapData
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle


class OccupancyGrid:
    """Read-only view over ``MapData`` with world/grid conversions."""

    def __init__(self, map_data: MapData, unknown_as_occupied: bool = True) -> None:
        self._map = map_data
        self._unknown_as_occupied = unknown_as_occupied

    @property
    def map_data(self) -> MapData:
        return self._map

    @property
    def width(self) -> int:
        return self._map.width

    @property
    def height(self) -> int:
        return self._map.height

    @property
    def resolution(self) -> float:
        return self._map.resolution

    @property
    def origin(self):
        return self._map.origin

    @property
    def unknown_as_occupied(self) -> bool:
        return self._unknown_as_occupied

    def world_to_grid(self, x: float, y: float) -> tuple[int, int] | None:
        """Return (row, col) of the cell containing the world point.

        Returns ``None`` when the point lies outside the map. Raises
        ``ValueError`` for NaN or infinite coordinates.
        """
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"coordinates must be finite, got ({x!r}, {y!r})")
        col = math.floor((x - self._map.origin.x) / self._map.resolution)
        row = math.floor((y - self._map.origin.y) / self._map.resolution)
        if 0 <= row < self._map.height and 0 <= col < self._map.width:
            return (row, col)
        return None

    def grid_to_world(self, row: int, col: int) -> Point2D:
        """Centre of cell (row, col) in world coordinates."""
        self._check_index(row, col)
        return Point2D(
            x=self._map.origin.x + (col + 0.5) * self._map.resolution,
            y=self._map.origin.y + (row + 0.5) * self._map.resolution,
        )

    def is_inside(self, x: float, y: float) -> bool:
        """True iff the world point falls inside the map bounds."""
        return self.world_to_grid(x, y) is not None

    def get_cell(self, row: int, col: int) -> CellState:
        """Cell state at (row, col); raises ``ValueError`` if out of range."""
        self._check_index(row, col)
        return CellState(self._map.cells[row * self._map.width + col])

    def is_blocked_cell(self, row: int, col: int) -> bool:
        """True iff the cell blocks the robot (OCCUPIED, or UNKNOWN per policy)."""
        state = self.get_cell(row, col)
        if state is CellState.OCCUPIED:
            return True
        return state is CellState.UNKNOWN and self._unknown_as_occupied

    def is_occupied(self, x: float, y: float) -> bool:
        """Occupancy at a world point; outside the map counts as occupied."""
        cell = self.world_to_grid(x, y)
        if cell is None:
            return True
        return self.is_blocked_cell(*cell)

    def inflate(self, radius: float) -> OccupancyGrid:
        """Return a new grid with OCCUPIED cells dilated by ``radius`` metres.

        Only OCCUPIED cells act as inflation sources. A cell (FREE or
        UNKNOWN) becomes OCCUPIED iff its centre lies within ``radius``
        of the centre of some source cell; UNKNOWN cells not covered by
        any source's inflation disk stay UNKNOWN. The original grid is
        never modified.
        """
        if not math.isfinite(radius) or radius < 0:
            raise ValueError(f"radius must be finite and non-negative, got {radius!r}")
        if radius == 0:
            return OccupancyGrid(self._map, self._unknown_as_occupied)

        resolution = self._map.resolution
        reach = math.ceil(radius / resolution)
        offsets = [
            (dr, dc)
            for dr in range(-reach, reach + 1)
            for dc in range(-reach, reach + 1)
            if math.hypot(dr, dc) * resolution <= radius + EPS
        ]

        width, height = self._map.width, self._map.height
        source_cells = self._map.cells
        new_cells = list(source_cells)
        for row in range(height):
            base = row * width
            for col in range(width):
                if source_cells[base + col] != CellState.OCCUPIED:
                    continue
                for dr, dc in offsets:
                    r, c = row + dr, col + dc
                    if 0 <= r < height and 0 <= c < width:
                        new_cells[r * width + c] = CellState.OCCUPIED.value

        inflated_map = self._map.model_copy(update={"cells": tuple(new_cells)})
        return OccupancyGrid(inflated_map, self._unknown_as_occupied)

    def _check_index(self, row: int, col: int) -> None:
        if not (0 <= row < self._map.height and 0 <= col < self._map.width):
            raise ValueError(
                f"cell index (row={row}, col={col}) out of range for "
                f"{self._map.height}x{self._map.width} grid"
            )


def rasterize_obstacles(
    map_data: MapData, obstacles: Iterable[CircleObstacle | RectangleObstacle]
) -> MapData:
    """Return a new ``MapData`` with shape obstacles burned in as OCCUPIED.

    A cell becomes OCCUPIED when the obstacle touches the cell's box
    (contact counts, consistent with the project collision rule).
    The input map is never modified.
    """
    width, height, resolution = map_data.width, map_data.height, map_data.resolution
    origin_x, origin_y = map_data.origin.x, map_data.origin.y
    cells = list(map_data.cells)

    def clamp_col(x: float) -> int:
        return min(width - 1, max(0, math.floor((x - origin_x) / resolution)))

    def clamp_row(y: float) -> int:
        return min(height - 1, max(0, math.floor((y - origin_y) / resolution)))

    for obstacle in obstacles:
        if isinstance(obstacle, CircleObstacle):
            min_x, max_x = obstacle.center.x - obstacle.radius, obstacle.center.x + obstacle.radius
            min_y, max_y = obstacle.center.y - obstacle.radius, obstacle.center.y + obstacle.radius
        elif isinstance(obstacle, RectangleObstacle):
            min_x, max_x = obstacle.min_x, obstacle.max_x
            min_y, max_y = obstacle.min_y, obstacle.max_y
        else:
            raise TypeError(f"unsupported obstacle type: {type(obstacle).__name__}")

        for row in range(clamp_row(min_y), clamp_row(max_y) + 1):
            cell_min_y = origin_y + row * resolution
            for col in range(clamp_col(min_x), clamp_col(max_x) + 1):
                cell_min_x = origin_x + col * resolution
                if isinstance(obstacle, CircleObstacle):
                    touches = (
                        distance_point_to_aabb(
                            obstacle.center.x,
                            obstacle.center.y,
                            cell_min_x,
                            cell_min_y,
                            cell_min_x + resolution,
                            cell_min_y + resolution,
                        )
                        <= obstacle.radius + EPS
                    )
                else:
                    touches = True  # the bounding-box range already is the overlap
                if touches:
                    cells[row * width + col] = CellState.OCCUPIED.value

    return map_data.model_copy(update={"cells": tuple(cells)})
