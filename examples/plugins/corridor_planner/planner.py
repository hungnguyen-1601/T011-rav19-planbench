"""A global planner nothing in the central dictionary knows about.

``ALGORITHMS`` in ``planbench_benchmark.registry`` is a Python dict, and
until H6 a global planner had to be an entry in it. This one is not:
the platform finds it by reading a manifest, loads it through the
trusted runtime, and drives it through the host's global contract.

The search itself is breadth-first on the grid the host granted —
complete on a finite grid, so "no path" from it means no path exists at
this resolution rather than that a sampler got unlucky. It exists to
prove the *boundary*, not to compete with A\\*: it optimises nothing, and
a report comparing the two would be comparing a demonstration with a
candidate.
"""

from __future__ import annotations

import math
from collections import deque

PLANNING_GRID = "planbench://channel/planning-grid@1"

#: Four-connected: diagonal moves through a grid corner can clip an
#: obstacle the cells themselves do not mark, and a demonstration should
#: not ship that subtlety.
_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class CorridorPlanner:
    """Breadth-first global planner, fed by the granted costmap channel."""

    def __init__(self, simplify: bool = True) -> None:
        self._simplify = simplify

    @property
    def name(self) -> str:
        return "corridor"

    def plan(self, request):
        from planbench_planning.common.base import PlanResult

        grid = _payload(request, PLANNING_GRID)
        start = grid.world_to_grid(*request.start)
        goal = grid.world_to_grid(*request.goal)
        if start is None or goal is None:
            return PlanResult(success=False, failure_reason="start or goal is off the map")

        came_from, expanded = _breadth_first(grid, start, goal)
        if goal not in came_from:
            return PlanResult(
                success=False,
                failure_reason="no four-connected route through the free cells",
                expanded_nodes=expanded,
            )

        cells = _trace_back(came_from, start, goal)
        if self._simplify:
            cells = _drop_collinear(cells)
        path = tuple(_to_point(grid, cell) for cell in cells)
        return PlanResult(
            success=True,
            path=path,
            path_length=_length(path),
            cost=float(len(cells)),
            expanded_nodes=expanded,
        )


def _payload(request, capability: str):
    for envelope in request.channels:
        if envelope.capability == capability:
            return envelope.payload
    raise LookupError(f"{capability!r} was not granted to corridor_planner")


def _breadth_first(grid, start, goal):
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    queue = deque([start])
    expanded = 0
    while queue:
        cell = queue.popleft()
        expanded += 1
        if cell == goal:
            break
        row, column = cell
        for d_row, d_column in _NEIGHBOURS:
            neighbour = (row + d_row, column + d_column)
            if neighbour in came_from:
                continue
            # Bounds first: ``is_blocked_cell`` raises off the map rather
            # than reporting blocked, and a search that walked off the
            # edge would die instead of turning around.
            if not (0 <= neighbour[0] < grid.height and 0 <= neighbour[1] < grid.width):
                continue
            if grid.is_blocked_cell(*neighbour):
                continue
            came_from[neighbour] = cell
            queue.append(neighbour)
    return came_from, expanded


def _trace_back(came_from, start, goal):
    cells = [goal]
    while cells[-1] != start:
        cells.append(came_from[cells[-1]])
    cells.reverse()
    return cells


def _drop_collinear(cells):
    """Keep only the corners. A path with one waypoint per cell makes a
    pure-pursuit follower chatter, and the geometry is identical."""
    if len(cells) < 3:
        return cells
    kept = [cells[0]]
    for previous, cell, following in zip(cells, cells[1:], cells[2:], strict=False):
        before = (cell[0] - previous[0], cell[1] - previous[1])
        after = (following[0] - cell[0], following[1] - cell[1])
        if before != after:
            kept.append(cell)
    kept.append(cells[-1])
    return kept


def _to_point(grid, cell):
    return grid.grid_to_world(*cell)


def _length(path) -> float:
    return sum(
        math.hypot(nxt.x - cur.x, nxt.y - cur.y)
        for cur, nxt in zip(path, path[1:], strict=False)
    )
