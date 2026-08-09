"""``L_ref``: the shortest path the map allows, per context (HĐ-6).

Every efficiency number in the system is a ratio against this length, so
what it means has to be decided once and stated plainly.

**It is a lower bound, on purpose.** The search runs on the *raw*
occupancy grid — only genuinely occupied (or unknown) cells are blocked,
with no inflation by the robot radius. A real robot keeps its radius away
from walls and therefore drives *further* than this, which is exactly the
property that makes the reference usable: ``path_efficiency = L_ref /
path_length`` stays in (0, 1], and HĐ-15.1's acceptance criterion
``L_ref <= path_length_m`` can be checked rather than hoped for.

Inflating the grid by the robot radius would read as more "realistic" and
is the wrong choice here: cell-wise inflation is coarser than the
collision test the simulator actually runs, so an inflated reference can
come out *longer* than a path the robot genuinely drove. A reference a
candidate can beat is not a reference — it silently turns a good run into
``path_efficiency > 1`` and breaks the anchor scale that HĐ-8 defines on
[0, 1].

**Dijkstra, not the A\\* the candidates use.** The reference must be a
property of the problem, not of anybody's planner: if the reference came
out of the same implementation (and the same tie-breaking, the same
heuristic) that one candidate runs, that candidate would be scored
against itself.

**The grid path is string-pulled before it is measured**, and that step
is not cosmetic. An 8-connected grid metric overestimates the true
continuous shortest path by up to ~8% on diagonal stretches — measured
on the reference warehouse, raw Dijkstra returns 47.8 m where an
string-pulled route is 45.4 m, and A\\* on the inflated grid plans 46.1 m
for the same mission. Quoting the raw grid cost as ``L_ref`` would
therefore have reported ``path_efficiency = 47.8 / 46.1 = 1.04`` for a
candidate that did *not* beat the optimum, and would have failed
HĐ-15.1's ``L_ref <= path_length_m`` on the very first episode of the
reference deployment. Line-of-sight shortcutting (the same
:func:`~planbench_planning.common.path_utils.simplify_path` the planners
use, on the same grid) removes the discretisation, leaving a residual
approximation far below the gap any real controller opens.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np

from planbench_planning.common.path_utils import path_length, simplify_path
from planbench_schemas.geometry import Point2D
from planbench_schemas.map import CellState, MapData
from planbench_simulator.grid import OccupancyGrid

__all__ = ["ReferencePathError", "clear_reference_cache", "reference_path_length"]

#: 8-connected neighbourhood: (drow, dcol, step cost in cells).
_NEIGHBOURS: tuple[tuple[int, int, float], ...] = (
    (-1, 0, 1.0),
    (1, 0, 1.0),
    (0, -1, 1.0),
    (0, 1, 1.0),
    (-1, -1, math.sqrt(2.0)),
    (-1, 1, math.sqrt(2.0)),
    (1, -1, math.sqrt(2.0)),
    (1, 1, math.sqrt(2.0)),
)


class ReferencePathError(ValueError):
    """The reference length cannot be computed for this context."""


@dataclass(frozen=True)
class _Key:
    map_name: str
    shape: tuple[int, int]
    resolution: float
    origin: tuple[float, float]
    start: tuple[int, int]
    goal: tuple[int, int]


_CACHE: dict[_Key, float | None] = {}


def clear_reference_cache() -> None:
    """Drop cached reference lengths. For tests and long processes."""
    _CACHE.clear()


def reference_path_length(
    map_data: MapData,
    start: Point2D,
    goal: Point2D,
) -> float | None:
    """``L_ref`` in metres, or ``None`` when the goal is unreachable.

    Cached per (map, start cell, goal cell): a context is run once per
    candidate and 300+ times per evaluation set, and the answer depends
    on none of that. ``None`` is a fact about the *profile*, not about a
    candidate — see :func:`planbench_metrics.definitions.compute_metrics`,
    which refuses to report an efficiency against a path that does not
    exist.
    """
    start_cell = _world_to_cell(map_data, start)
    goal_cell = _world_to_cell(map_data, goal)
    if start_cell is None or goal_cell is None:
        raise ReferencePathError(
            f"start {(start.x, start.y)} or goal {(goal.x, goal.y)} lies outside map "
            f"{map_data.name!r}; the profile and the map disagree (see "
            "planbench_benchmark.task_map.validate_missions_on_map)"
        )

    key = _Key(
        map_name=map_data.name,
        shape=(map_data.height, map_data.width),
        resolution=map_data.resolution,
        origin=(map_data.origin.x, map_data.origin.y),
        start=start_cell,
        goal=goal_cell,
    )
    if key in _CACHE:
        return _CACHE[key]

    blocked = _blocked_mask(map_data)
    if blocked[start_cell] or blocked[goal_cell]:
        raise ReferencePathError(
            f"start or goal is on a blocked cell of map {map_data.name!r}; no reference "
            "path exists because the mission itself is impossible, not because a "
            "candidate failed"
        )

    cell_path = _dijkstra_path(blocked, start_cell, goal_cell)
    if cell_path is None:
        _CACHE[key] = None
        return None

    grid = OccupancyGrid(map_data)
    polyline = [_cell_to_world(map_data, cell) for cell in cell_path]
    # Anchor the ends at the real mission poses: the first and last cell
    # centres are up to half a cell away from them, and that offset would
    # otherwise sit in every efficiency ratio on this context.
    polyline[0] = Point2D(x=start.x, y=start.y)
    polyline[-1] = Point2D(x=goal.x, y=goal.y)
    length = path_length(simplify_path(grid, polyline))
    _CACHE[key] = length
    return length


def _world_to_cell(map_data: MapData, point: Point2D) -> tuple[int, int] | None:
    col = int((point.x - map_data.origin.x) / map_data.resolution)
    row = int((point.y - map_data.origin.y) / map_data.resolution)
    if 0 <= row < map_data.height and 0 <= col < map_data.width:
        return (row, col)
    return None


def _blocked_mask(map_data: MapData) -> np.ndarray:
    """Occupied *and* unknown cells are blocked.

    Unknown counts as blocked for the same reason it does everywhere else
    in this codebase: a cell nobody surveyed is not a cell to route
    through, and a reference path that shortcuts through unsurveyed space
    would make every candidate look worse than it is.
    """
    cells = np.asarray(map_data.cells, dtype=np.int16).reshape(map_data.height, map_data.width)
    return cells != CellState.FREE.value


def _cell_to_world(map_data: MapData, cell: tuple[int, int]) -> Point2D:
    row, col = cell
    return Point2D(
        x=map_data.origin.x + (col + 0.5) * map_data.resolution,
        y=map_data.origin.y + (row + 0.5) * map_data.resolution,
    )


def _dijkstra_path(
    blocked: np.ndarray, start: tuple[int, int], goal: tuple[int, int]
) -> list[tuple[int, int]] | None:
    """Shortest 8-connected cell path, or None when unreachable.

    Diagonal moves are refused when both orthogonal neighbours are
    blocked: slipping through the corner contact of two walls is a route
    no vehicle can drive, and a reference that uses it is shorter than
    anything achievable.
    """
    height, width = blocked.shape
    distance = np.full((height, width), math.inf, dtype=np.float64)
    visited = np.zeros((height, width), dtype=bool)
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    distance[start] = 0.0
    queue: list[tuple[float, int, int]] = [(0.0, start[0], start[1])]

    while queue:
        cost, row, col = heapq.heappop(queue)
        if visited[row, col]:
            continue
        visited[row, col] = True
        if (row, col) == goal:
            return _reconstruct(parent, start, goal)
        for drow, dcol, step in _NEIGHBOURS:
            nrow, ncol = row + drow, col + dcol
            if not (0 <= nrow < height and 0 <= ncol < width):
                continue
            if blocked[nrow, ncol] or visited[nrow, ncol]:
                continue
            if drow != 0 and dcol != 0 and blocked[row, ncol] and blocked[nrow, col]:
                continue
            new_cost = cost + step
            if new_cost < distance[nrow, ncol]:
                distance[nrow, ncol] = new_cost
                parent[(nrow, ncol)] = (row, col)
                heapq.heappush(queue, (new_cost, nrow, ncol))
    return None


def _reconstruct(
    parent: dict[tuple[int, int], tuple[int, int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return path
