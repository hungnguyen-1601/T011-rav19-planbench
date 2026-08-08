"""RRT* sampling-based global planner.

Deterministic *given the config seed*: every random draw comes from a
:class:`numpy.random.Generator` built from ``config.seed`` (and, when
the caller supplies one, the episode seed). The global ``random``
module is never touched — its state is process-wide, so two episodes
running in the same process would contaminate each other and the run
would stop being reproducible.

The planner treats the given grid as configuration space — callers
inflate obstacles by the robot radius before planning. Collision checks
are done on whole segments (``has_line_of_sight``), not on vertices, so
an edge can never jump across a thin wall.

Unlike A*, the search does not stop at the first solution: the loop
always runs its full iteration budget and keeps rewiring, which is what
makes the result improve with ``max_iterations`` (asymptotic
optimality) rather than merely arrive sooner.
"""

from __future__ import annotations

import math
import time

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_planning.common.path_utils import has_line_of_sight, path_length
from planbench_schemas.geometry import Point2D, euclidean_distance
from planbench_simulator.grid import OccupancyGrid


class RRTStarConfig(BaseModel):
    """RRT* options. All distances are in metres.

    The fields are also the tuning search space (P01): declaring them up
    front means a later Optuna study does not need the planner to change.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    max_iterations: int = Field(default=3000, gt=0)
    step_size: float = Field(default=0.5, gt=0.0)
    goal_bias: float = Field(default=0.05, ge=0.0, le=1.0)
    rewire_radius: float = Field(default=1.5, gt=0.0)
    goal_tolerance: float = Field(default=0.3, gt=0.0)
    #: Seed of the planner's own randomness — distinct from the episode
    #: seed, which drives the dynamic obstacles. See ``RRTStarPlanner``.
    seed: int = Field(default=0, ge=0)


class RRTStarPlanner(GlobalPlanner):
    """RRT* on an occupancy grid.

    ``episode_seed`` is the benchmark's per-episode seed. It is mixed
    into the planner's generator so that a benchmark sweeping 30 seeds
    actually grows 30 different trees — with a fixed planner seed alone
    every episode would replay the same tree, and running a randomised
    planner over many seeds would measure nothing.

    The two seeds are combined through a ``SeedSequence`` rather than
    XOR: XOR collides (``1 ^ 2`` and ``3 ^ 0`` draw the same numbers),
    which would silently pair up episodes meant to be independent.
    """

    def __init__(self, config: RRTStarConfig | None = None, *, episode_seed: int = 0) -> None:
        self._config = config or RRTStarConfig()
        self._episode_seed = episode_seed

    @property
    def name(self) -> str:
        return "rrtstar"

    @property
    def config(self) -> RRTStarConfig:
        return self._config

    @property
    def episode_seed(self) -> int:
        return self._episode_seed

    def plan(self, grid: OccupancyGrid, start: Point2D, goal: Point2D) -> PlanResult:
        started_at = time.perf_counter()
        config = self._config
        node_count = 0

        def fail(reason: str) -> PlanResult:
            return PlanResult(
                success=False,
                failure_reason=reason,
                expanded_nodes=node_count,
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
            return PlanResult(
                success=True,
                path=(start, goal),
                path_length=euclidean_distance(start, goal),
                cost=0.0,
                expanded_nodes=0,
                planning_time_seconds=time.perf_counter() - started_at,
            )

        rng = np.random.default_rng(np.random.SeedSequence([config.seed, self._episode_seed]))
        min_x, min_y = grid.origin.x, grid.origin.y
        max_x = min_x + grid.width * grid.resolution
        max_y = min_y + grid.height * grid.resolution

        # Tree state. Coordinates live in preallocated numpy arrays so
        # the nearest/near queries stay vectorised and no reallocation
        # happens inside the loop; the topology is plain Python lists,
        # touched one node at a time.
        capacity = config.max_iterations + 1
        xs = np.empty(capacity, dtype=float)
        ys = np.empty(capacity, dtype=float)
        xs[0], ys[0] = start.x, start.y
        parents: list[int] = [-1]
        children: list[list[int]] = [[]]
        costs: list[float] = [0.0]
        node_count = 1

        best_goal_parent = -1
        best_goal_cost = math.inf

        for _ in range(config.max_iterations):
            if rng.random() < config.goal_bias:
                sample_x, sample_y = goal.x, goal.y
            else:
                sample_x = float(rng.uniform(min_x, max_x))
                sample_y = float(rng.uniform(min_y, max_y))
                if grid.is_occupied(sample_x, sample_y):
                    continue

            tree_x, tree_y = xs[:node_count], ys[:node_count]
            distances = np.hypot(tree_x - sample_x, tree_y - sample_y)
            nearest = int(np.argmin(distances))
            nearest_distance = float(distances[nearest])
            if nearest_distance <= 1e-12:
                continue

            # Steer: a step of at most step_size towards the sample.
            scale = min(config.step_size, nearest_distance) / nearest_distance
            new_x = float(xs[nearest] + (sample_x - xs[nearest]) * scale)
            new_y = float(ys[nearest] + (sample_y - ys[nearest]) * scale)
            new_point = Point2D(x=new_x, y=new_y)
            if grid.is_occupied(new_x, new_y):
                continue

            near_distances = np.hypot(tree_x - new_x, tree_y - new_y)
            near = [int(index) for index in np.flatnonzero(near_distances <= config.rewire_radius)]

            # Cheapest reachable parent. Candidates are tried in
            # ascending total cost, so the first one with line of sight
            # is the best one — usually a single collision check. The
            # index is part of the sort key to keep ties deterministic.
            candidates = sorted(
                (costs[index] + float(near_distances[index]), index) for index in near
            )
            if not candidates:  # step_size larger than rewire_radius
                candidates = [(costs[nearest] + nearest_distance, nearest)]
            parent = -1
            parent_cost = math.inf
            for candidate_cost, index in candidates:
                if has_line_of_sight(grid, Point2D(x=xs[index], y=ys[index]), new_point):
                    parent, parent_cost = index, candidate_cost
                    break
            if parent < 0:
                continue

            new_index = node_count
            xs[new_index], ys[new_index] = new_x, new_y
            parents.append(parent)
            children.append([])
            children[parent].append(new_index)
            costs.append(parent_cost)
            node_count += 1

            # Rewire: only nodes that would actually get cheaper are
            # worth a collision check.
            for index in near:
                if index == parent:
                    continue
                rewired_cost = parent_cost + float(near_distances[index])
                if rewired_cost >= costs[index]:
                    continue
                if not has_line_of_sight(grid, new_point, Point2D(x=xs[index], y=ys[index])):
                    continue
                children[parents[index]].remove(index)
                parents[index] = new_index
                children[new_index].append(index)
                _propagate_cost(children, costs, index, rewired_cost)

            goal_distance = euclidean_distance(new_point, goal)
            if goal_distance <= config.goal_tolerance:
                goal_cost = parent_cost + goal_distance
                if goal_cost < best_goal_cost and has_line_of_sight(grid, new_point, goal):
                    best_goal_cost = goal_cost
                    best_goal_parent = new_index

        if best_goal_parent < 0:
            return fail("no path found within the iteration budget")

        waypoints: list[Point2D] = []
        index = best_goal_parent
        while index >= 0:
            waypoints.append(Point2D(x=float(xs[index]), y=float(ys[index])))
            index = parents[index]
        waypoints.reverse()
        # waypoints[0] is the tree root, which sits exactly on start.
        waypoints.append(goal)
        path = tuple(waypoints)
        # Rewiring can have made the goal branch cheaper after it was
        # recorded, so read the cost back off the tree.
        cost = costs[best_goal_parent] + euclidean_distance(path[-2], goal)
        return PlanResult(
            success=True,
            path=path,
            path_length=path_length(path),
            cost=cost,
            expanded_nodes=node_count,
            planning_time_seconds=time.perf_counter() - started_at,
        )


def _propagate_cost(
    children: list[list[int]], costs: list[float], root: int, new_cost: float
) -> None:
    """Apply a cost improvement at ``root`` to its whole subtree.

    Skipping this is the classic RRT* bug: the tree keeps stale costs,
    later parent choices compare against numbers that are no longer
    true, and the path stops improving with the iteration budget.
    """
    delta = new_cost - costs[root]
    costs[root] = new_cost
    if delta == 0.0:
        return
    stack = list(children[root])
    while stack:
        index = stack.pop()
        costs[index] += delta
        stack.extend(children[index])
