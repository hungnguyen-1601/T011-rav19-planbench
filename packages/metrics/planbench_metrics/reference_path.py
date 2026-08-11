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
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from planbench_planning.common.path_utils import (
    has_line_of_sight,
    path_length,
    simplify_path,
)
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
    # Every segment of what ``_taut`` returns has been line-of-sight
    # checked, so this length is that of a path the map genuinely allows.
    length = path_length(_taut(grid, polyline))
    _CACHE[key] = length
    return length


#: Sweeps over the whole ladder of scales. Two is enough on both
#: reference maps — a third changed nothing to five decimals — and the
#: loop exits early anyway once a sweep stops moving anything.
_TAUT_SWEEPS = 2

#: Bisection steps per vertex. Each halves the interval, so 16 resolves a
#: 24 m hall to ~0.4 mm, three orders below anything the metric reports.
#: A fixed count rather than a tolerance loop: HĐ-15.1(2) wants the same
#: six decimals on every re-run, and "iterate until it stops changing" on
#: floating point is where that quietly stops holding.
_TAUT_BISECTIONS = 16

#: A move worth making. Also the early-exit test, which is why it is
#: 0.1 mm rather than machine epsilon: a path that is already taut still
#: jitters in the last bits forever, and without a floor the sweep never
#: reports itself finished.
_TAUT_EPS_M = 1e-4


def _taut(grid: OccupancyGrid, polyline: Sequence[Point2D]) -> tuple[Point2D, ...]:
    """Pull a grid path taut, the way a string round the obstacles would.

    **Why greedy shortcutting alone is not enough** — this function
    exists to fix a measured error, not a theoretical one.
    :func:`simplify_path` can only pick from the vertices it is given,
    and those are *cell centres*. Rounding a convex corner, the taut
    route touches the corner itself; the nearest cell centre sits up to
    half a cell outside it. Worse, the greedy rule keeps the *farthest*
    visible vertex, which on the far side of an obstacle can skip past
    the corner the string actually needs to bend at.

    Measured on the reference hall, where the optimum is known
    analytically (two legs round one rectangular block): true optimum
    20.2788 m, shortcutting alone 20.7679 m — **+2.41%**. That is larger
    than the 0.20 m goal tolerance, so it failed HĐ-15.1(5) on a route
    the robot drove perfectly well, and it is the dangerous kind of
    failure: ``path_efficiency = L_ref / path_length`` would exceed 1 and
    be clipped, reporting a good run as a perfect one, with the error
    reading as a property of the candidate.

    **Multi-scale, because purely local relaxation does not converge in
    useful time.** Pulling each vertex toward the chord of its immediate
    neighbours is a diffusion: information crawls one vertex per sweep,
    and on the hall's 401-vertex path 150 sweeps still left +1.35%. So
    the pull runs at every scale — neighbours at distance n/2, n/4, …, 1.
    The coarse scales move whole arcs at once and place the path against
    the corners; the fine scales clean up. Two sweeps of the full ladder
    land at **+0.00055 m (+0.0027%)** on the hall, and leave the
    warehouse route unchanged to five decimals, that one having been
    taut already.

    **Correctness does not rest on this converging.** The caller measures
    ``simplify_path`` of the result, and every segment that comes out of
    it is line-of-sight checked against the grid. Relaxation can only
    *guide* where the vertices sit; it cannot produce a length shorter
    than a real free path, however badly it behaves.

    The reference stays **un-inflated** (see the module docstring): the
    shortest path for a point, which is what makes it a property of the
    problem rather than of somebody's safety margin. A taut path touching
    a corner is therefore correct, not a violation.
    """
    points = [(point.x, point.y) for point in polyline]
    for _ in range(_TAUT_SWEEPS):
        moved = False
        for stride in _strides(len(points)):
            for index in range(stride, len(points) - stride):
                pulled = _pull_vertex(
                    grid, points[index - stride], points[index], points[index + stride]
                )
                if pulled is not None:
                    points[index] = pulled
                    moved = True
        if not moved:
            break
    return simplify_path(grid, [Point2D(x=x, y=y) for x, y in points])


def _strides(count: int) -> list[int]:
    """Neighbour distances to pull against: ``n/2, n/4, … 1``."""
    strides: list[int] = []
    stride = max(1, count // 2)
    while stride >= 1:
        strides.append(stride)
        stride //= 2
    return strides


def _pull_vertex(
    grid: OccupancyGrid,
    before: tuple[float, float],
    vertex: tuple[float, float],
    after: tuple[float, float],
) -> tuple[float, float] | None:
    """Slide one vertex toward the line through its two neighbours.

    Returns the new position, or ``None`` when it cannot usefully move.
    The target is the foot of the perpendicular — the direction that
    shortens both legs fastest — and the distance travelled is found by
    bisection, because the far end is typically inside an obstacle while
    the near end is free. The boundary between them is where the string
    comes to rest against the corner.
    """
    target = _foot_of_perpendicular(before, vertex, after)
    if math.dist(vertex, target) < _TAUT_EPS_M:
        return None

    low, high = 0.0, 1.0
    best: tuple[float, float] | None = None
    for _ in range(_TAUT_BISECTIONS):
        middle = (low + high) / 2.0
        candidate = (
            vertex[0] + (target[0] - vertex[0]) * middle,
            vertex[1] + (target[1] - vertex[1]) * middle,
        )
        if _visible(grid, before, candidate) and _visible(grid, candidate, after):
            best = candidate
            low = middle
        else:
            high = middle

    if best is None or math.dist(vertex, best) < _TAUT_EPS_M:
        return None
    return best


def _visible(grid: OccupancyGrid, a: tuple[float, float], b: tuple[float, float]) -> bool:
    return has_line_of_sight(grid, Point2D(x=a[0], y=a[1]), Point2D(x=b[0], y=b[1]))


def _foot_of_perpendicular(
    before: tuple[float, float], vertex: tuple[float, float], after: tuple[float, float]
) -> tuple[float, float]:
    """Closest point to ``vertex`` on the segment ``before``–``after``.

    Clamped to the segment: past its ends the perpendicular foot is no
    longer between the neighbours, and pulling there would lengthen the
    path rather than shorten it.
    """
    dx = after[0] - before[0]
    dy = after[1] - before[1]
    span = dx * dx + dy * dy
    if span == 0.0:
        return before
    t = ((vertex[0] - before[0]) * dx + (vertex[1] - before[1]) * dy) / span
    t = min(1.0, max(0.0, t))
    return (before[0] + dx * t, before[1] + dy * t)


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
