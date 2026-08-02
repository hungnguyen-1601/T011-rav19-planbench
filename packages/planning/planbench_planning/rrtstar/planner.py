"""RRT* global planner — sampling-based alternative to A*.

Deterministic for identical inputs: the config carries its own
``seed``, and ``plan()`` builds a fresh ``random.Random(seed)`` on each
call (never a shared instance), so calling the same config twice on
the same grid/start/goal always produces the same tree and path.

The planner treats the given grid as configuration space — same
contract as :class:`~planbench_planning.astar.planner.AStarPlanner`:
callers inflate obstacles by the robot radius before planning.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_planning.common.path_utils import has_line_of_sight, path_length, simplify_path
from planbench_schemas.geometry import Point2D, euclidean_distance
from planbench_simulator.grid import OccupancyGrid


class RRTStarConfig(BaseModel):
    """RRT* options.

    ``seed`` lives on the config (not threaded from the scenario) so a
    planner instance stays deterministic on its own — see the module
    docstring. That means every benchmark seed produces the same RRT*
    tree; there is no per-seed path diversity (see
    docs/KNOWN_LIMITATIONS.md).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    max_iterations: int = Field(default=1500, gt=0)
    step_size: float = Field(default=0.5, gt=0)
    goal_bias: float = Field(default=0.1, ge=0, le=1)
    rewire_radius: float = Field(default=1.0, gt=0)
    goal_tolerance: float = Field(default=0.3, gt=0)
    simplify: bool = Field(default=True)
    seed: int = Field(default=0)


@dataclass
class _Node:
    point: Point2D
    parent: int | None
    cost: float


class RRTStarPlanner(GlobalPlanner):
    """Sampling-based global planner with rewiring (Karaman & Frazzoli).

    ``expanded_nodes`` in the returned :class:`PlanResult` counts tree
    nodes added, not a "closed set" — not directly comparable to A*'s
    ``expanded_nodes`` (see docs/KNOWN_LIMITATIONS.md).
    """

    def __init__(self, config: RRTStarConfig | None = None) -> None:
        self._config = config or RRTStarConfig()

    @property
    def config(self) -> RRTStarConfig:
        return self._config

    @property
    def name(self) -> str:
        return "rrtstar"

    def plan(self, grid: OccupancyGrid, start: Point2D, goal: Point2D) -> PlanResult:
        started_at = time.perf_counter()
        config = self._config

        def fail(reason: str, expanded: int = 0) -> PlanResult:
            return PlanResult(
                success=False,
                failure_reason=reason,
                expanded_nodes=expanded,
                planning_time_seconds=time.perf_counter() - started_at,
            )

        if grid.world_to_grid(start.x, start.y) is None:
            return fail("start is outside the map")
        if grid.world_to_grid(goal.x, goal.y) is None:
            return fail("goal is outside the map")
        if grid.is_occupied(start.x, start.y):
            return fail("start is inside an obstacle")
        if grid.is_occupied(goal.x, goal.y):
            return fail("goal is inside an obstacle")

        if euclidean_distance(start, goal) <= config.goal_tolerance:
            path = (start, goal)
            return PlanResult(
                success=True,
                path=path,
                path_length=euclidean_distance(start, goal),
                cost=0.0,
                expanded_nodes=0,
                planning_time_seconds=time.perf_counter() - started_at,
            )

        rng = random.Random(config.seed)
        min_x = grid.origin.x
        min_y = grid.origin.y
        max_x = grid.origin.x + grid.width * grid.resolution
        max_y = grid.origin.y + grid.height * grid.resolution

        nodes: list[_Node] = [_Node(point=start, parent=None, cost=0.0)]
        best_goal_index: int | None = None
        best_goal_cost = math.inf

        for _ in range(config.max_iterations):
            if rng.random() < config.goal_bias:
                sample = goal
            else:
                sample = Point2D(x=rng.uniform(min_x, max_x), y=rng.uniform(min_y, max_y))

            nearest_index = self._nearest(nodes, sample)
            nearest = nodes[nearest_index]
            new_point = self._steer(nearest.point, sample, config.step_size)

            if not has_line_of_sight(grid, nearest.point, new_point):
                continue

            near_indices = [
                i
                for i, node in enumerate(nodes)
                if euclidean_distance(node.point, new_point) <= config.rewire_radius
            ]
            if nearest_index not in near_indices:
                near_indices.append(nearest_index)

            parent_index = nearest_index
            parent_cost = nearest.cost + euclidean_distance(nearest.point, new_point)
            for i in near_indices:
                candidate_cost = nodes[i].cost + euclidean_distance(nodes[i].point, new_point)
                if candidate_cost < parent_cost and has_line_of_sight(grid, nodes[i].point, new_point):
                    parent_index, parent_cost = i, candidate_cost

            nodes.append(_Node(point=new_point, parent=parent_index, cost=parent_cost))
            new_index = len(nodes) - 1

            for i in near_indices:
                if i == parent_index:
                    continue
                rewired_cost = parent_cost + euclidean_distance(new_point, nodes[i].point)
                if rewired_cost < nodes[i].cost and has_line_of_sight(grid, new_point, nodes[i].point):
                    nodes[i].parent = new_index
                    nodes[i].cost = rewired_cost

            distance_to_goal = euclidean_distance(new_point, goal)
            if distance_to_goal <= config.goal_tolerance and has_line_of_sight(grid, new_point, goal):
                goal_cost = parent_cost + distance_to_goal
                if goal_cost < best_goal_cost:
                    best_goal_cost = goal_cost
                    best_goal_index = new_index

        if best_goal_index is None:
            return fail("no path found within max_iterations", expanded=len(nodes) - 1)

        waypoints: list[Point2D] = [goal]
        index: int | None = best_goal_index
        while index is not None:
            waypoints.append(nodes[index].point)
            index = nodes[index].parent
        waypoints.reverse()

        path = simplify_path(grid, waypoints) if config.simplify else tuple(waypoints)
        return PlanResult(
            success=True,
            path=path,
            path_length=path_length(path),
            cost=best_goal_cost,
            expanded_nodes=len(nodes) - 1,
            planning_time_seconds=time.perf_counter() - started_at,
        )

    @staticmethod
    def _nearest(nodes: list[_Node], sample: Point2D) -> int:
        best_index = 0
        best_distance = math.inf
        for i, node in enumerate(nodes):
            distance = euclidean_distance(node.point, sample)
            if distance < best_distance:
                best_index, best_distance = i, distance
        return best_index

    @staticmethod
    def _steer(origin: Point2D, target: Point2D, step_size: float) -> Point2D:
        distance = euclidean_distance(origin, target)
        if distance <= step_size:
            return target
        t = step_size / distance
        return Point2D(x=origin.x + (target.x - origin.x) * t, y=origin.y + (target.y - origin.y) * t)
