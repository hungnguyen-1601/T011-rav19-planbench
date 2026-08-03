"""Tests for the A* global planner (all mandatory spec cases)."""

from __future__ import annotations

import pytest

from planbench_planning import AStarConfig, AStarPlanner, has_line_of_sight
from planbench_schemas.geometry import Point2D, euclidean_distance
from planbench_simulator.grid import OccupancyGrid


def p(x: float, y: float) -> Point2D:
    return Point2D(x=x, y=y)


def assert_path_valid(grid: OccupancyGrid, path: tuple[Point2D, ...]) -> None:
    """Every consecutive segment must stay in free space."""
    assert len(path) >= 2
    for a, b in zip(path, path[1:], strict=False):
        assert has_line_of_sight(grid, a, b), f"segment {a} -> {b} crosses an obstacle"


@pytest.fixture
def planner() -> AStarPlanner:
    return AStarPlanner()


class TestAStarSuccess:
    def test_empty_map(self, map_factory, planner: AStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner.plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert result.success
        assert result.path[0] == p(1.5, 1.5)
        assert result.path[-1] == p(8.5, 8.5)
        assert result.path_length >= euclidean_distance(p(1.5, 1.5), p(8.5, 8.5)) - 1e-9
        assert result.expanded_nodes > 0
        assert_path_valid(grid, result.path)

    def test_wall_with_gap(self, map_factory, planner: AStarPlanner) -> None:
        # Wall col=5, gap at row 9 -> path must detour through the gap.
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(9))))
        result = planner.plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert result.success
        assert_path_valid(grid, result.path)
        direct = euclidean_distance(p(2.5, 2.5), p(8.5, 2.5))
        assert result.path_length > direct  # forced detour

    def test_start_equals_goal_cell(self, map_factory, planner: AStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5))
        result = planner.plan(grid, p(2.2, 2.2), p(2.8, 2.8))  # same cell (2, 2)
        assert result.success
        assert result.path == (p(2.2, 2.2), p(2.8, 2.8))
        assert result.cost == 0.0

    def test_four_connected_manhattan(self, map_factory) -> None:
        planner = AStarPlanner(AStarConfig(connectivity=4, heuristic="manhattan"))
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner.plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert result.success
        assert_path_valid(grid, result.path)

    def test_no_simplification_keeps_cell_centres(self, map_factory) -> None:
        planner = AStarPlanner(AStarConfig(simplify=False))
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner.plan(grid, p(1.5, 1.5), p(1.5, 4.5))
        assert result.success
        assert len(result.path) >= 4  # start + cell centres + goal


class TestAStarFailures:
    def test_no_path(self, map_factory, planner: AStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(10))))
        result = planner.plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert not result.success
        assert "no path" in result.failure_reason
        assert result.expanded_nodes > 0

    def test_start_outside_map(self, map_factory, planner: AStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5))
        result = planner.plan(grid, p(-1.0, 2.5), p(2.5, 2.5))
        assert not result.success
        assert "start is outside" in result.failure_reason

    def test_goal_outside_map(self, map_factory, planner: AStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5))
        result = planner.plan(grid, p(2.5, 2.5), p(7.0, 2.5))
        assert not result.success
        assert "goal is outside" in result.failure_reason

    def test_start_in_obstacle(self, map_factory, planner: AStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),)))
        result = planner.plan(grid, p(2.5, 2.5), p(4.5, 4.5))
        assert not result.success
        assert "start is inside an obstacle" in result.failure_reason

    def test_goal_in_obstacle(self, map_factory, planner: AStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),)))
        result = planner.plan(grid, p(0.5, 0.5), p(2.5, 2.5))
        assert not result.success
        assert "goal is inside an obstacle" in result.failure_reason

    def test_unknown_cells_block_planning_by_default(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10, unknown=tuple((row, 5) for row in range(10))))
        result = AStarPlanner().plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert not result.success


class TestAStarDeterminism:
    def test_identical_inputs_identical_paths(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(9))))
        first = AStarPlanner().plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        second = AStarPlanner().plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert first.success and second.success
        assert first.path == second.path
        assert first.cost == second.cost
        assert first.expanded_nodes == second.expanded_nodes
