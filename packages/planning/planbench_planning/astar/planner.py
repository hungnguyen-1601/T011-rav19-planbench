"""Grid-based A* global planner.

Deterministic: fixed neighbour ordering and an insertion counter as the
heap tie-breaker guarantee identical paths for identical inputs.

The planner treats the given grid as configuration space — callers
inflate obstacles by the robot radius before planning.
"""

from __future__ import annotations

import heapq
import itertools
import math
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict

from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_planning.common.path_utils import path_length, simplify_path
from planbench_schemas.geometry import Point2D, euclidean_distance
from planbench_simulator.grid import OccupancyGrid

_SQRT2 = math.sqrt(2.0)
# Fixed order matters for determinism: E, W, N, S then the diagonals.
_CARDINAL = ((0, 1), (0, -1), (1, 0), (-1, 0))
_DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))


class AStarConfig(BaseModel):
    """A* options.

    ``manhattan`` is admissible for 4-connected grids only; with
    8-connectivity it may overestimate and yield non-optimal (still
    valid) paths — prefer ``euclidean`` there.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    connectivity: Literal[4, 8] = 8
    heuristic: Literal["manhattan", "euclidean"] = "euclidean"
    simplify: bool = True


class AStarPlanner(GlobalPlanner):
    """A* on an occupancy grid with optional line-of-sight simplification."""

    def __init__(self, config: AStarConfig | None = None) -> None:
        self._config = config or AStarConfig()

    @property
    def config(self) -> AStarConfig:
        return self._config

    @property
    def name(self) -> str:
        return "astar"

    def plan(self, grid: OccupancyGrid, start: Point2D, goal: Point2D) -> PlanResult:
        started_at = time.perf_counter()
        expanded = 0

        def fail(reason: str) -> PlanResult:
            return PlanResult(
                success=False,
                failure_reason=reason,
                expanded_nodes=expanded,
                planning_time_seconds=time.perf_counter() - started_at,
            )

        start_cell = grid.world_to_grid(start.x, start.y)
        if start_cell is None:
            return fail("start is outside the map")
        goal_cell = grid.world_to_grid(goal.x, goal.y)
        if goal_cell is None:
            return fail("goal is outside the map")
        if grid.is_blocked_cell(*start_cell):
            return fail("start is inside an obstacle")
        if grid.is_blocked_cell(*goal_cell):
            return fail("goal is inside an obstacle")

        if start_cell == goal_cell:
            path = (start, goal)
            return PlanResult(
                success=True,
                path=path,
                path_length=euclidean_distance(start, goal),
                cost=0.0,
                expanded_nodes=0,
                planning_time_seconds=time.perf_counter() - started_at,
            )

        heuristic = self._make_heuristic(goal_cell)
        counter = itertools.count()
        open_heap: list[tuple[float, float, int, tuple[int, int]]] = [
            (heuristic(start_cell), 0.0, next(counter), start_cell)
        ]
        g_score: dict[tuple[int, int], float] = {start_cell: 0.0}
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        closed: set[tuple[int, int]] = set()

        while open_heap:
            _, current_g, _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            expanded += 1
            if current == goal_cell:
                return self._build_result(
                    grid, start, goal, came_from, goal_cell, current_g, expanded, started_at
                )
            row, col = current
            for delta_row, delta_col, step_cost in self._neighbours(grid, row, col):
                neighbour = (row + delta_row, col + delta_col)
                if neighbour in closed:
                    continue
                tentative_g = current_g + step_cost
                if tentative_g < g_score.get(neighbour, math.inf):
                    g_score[neighbour] = tentative_g
                    came_from[neighbour] = current
                    heapq.heappush(
                        open_heap,
                        (tentative_g + heuristic(neighbour), tentative_g, next(counter), neighbour),
                    )

        return fail("no path exists between start and goal")

    def _neighbours(self, grid: OccupancyGrid, row: int, col: int):
        """Yield (delta_row, delta_col, step_cost) for free neighbours.

        Diagonal moves are blocked when either adjacent cardinal cell is
        blocked (no corner cutting).
        """

        def free(r: int, c: int) -> bool:
            return 0 <= r < grid.height and 0 <= c < grid.width and not grid.is_blocked_cell(r, c)

        for delta_row, delta_col in _CARDINAL:
            if free(row + delta_row, col + delta_col):
                yield delta_row, delta_col, 1.0
        if self._config.connectivity == 8:
            for delta_row, delta_col in _DIAGONAL:
                if (
                    free(row + delta_row, col + delta_col)
                    and free(row + delta_row, col)
                    and free(row, col + delta_col)
                ):
                    yield delta_row, delta_col, _SQRT2

    def _make_heuristic(self, goal_cell: tuple[int, int]):
        goal_row, goal_col = goal_cell
        if self._config.heuristic == "manhattan":
            return lambda cell: abs(cell[0] - goal_row) + abs(cell[1] - goal_col)
        return lambda cell: math.hypot(cell[0] - goal_row, cell[1] - goal_col)

    def _build_result(
        self,
        grid: OccupancyGrid,
        start: Point2D,
        goal: Point2D,
        came_from: dict[tuple[int, int], tuple[int, int]],
        goal_cell: tuple[int, int],
        goal_g: float,
        expanded: int,
        started_at: float,
    ) -> PlanResult:
        cells = [goal_cell]
        while cells[-1] in came_from:
            cells.append(came_from[cells[-1]])
        cells.reverse()
        waypoints = [start]
        waypoints.extend(grid.grid_to_world(row, col) for row, col in cells)
        waypoints.append(goal)
        path = simplify_path(grid, waypoints) if self._config.simplify else tuple(waypoints)
        return PlanResult(
            success=True,
            path=path,
            path_length=path_length(path),
            cost=goal_g * grid.resolution,
            expanded_nodes=expanded,
            planning_time_seconds=time.perf_counter() - started_at,
        )
