"""Tests for the RRT* global planner."""

from __future__ import annotations

import pytest

from planbench_planning import RRTStarConfig, RRTStarPlanner, has_line_of_sight
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
def planner() -> RRTStarPlanner:
    return RRTStarPlanner(RRTStarConfig(max_iterations=800, seed=1))


class TestRRTStarSuccess:
    def test_empty_map(self, map_factory, planner: RRTStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner.plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert result.success
        assert result.path[0] == p(1.5, 1.5)
        assert result.path[-1] == p(8.5, 8.5)
        assert result.path_length >= euclidean_distance(p(1.5, 1.5), p(8.5, 8.5)) - 1e-9
        assert result.expanded_nodes > 0
        assert_path_valid(grid, result.path)

    def test_wall_with_gap(self, map_factory) -> None:
        # Wall col=5, gap at row 9 -> path must detour through the gap.
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(9))))
        planner = RRTStarPlanner(RRTStarConfig(max_iterations=1500, seed=1))
        result = planner.plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert result.success
        assert_path_valid(grid, result.path)
        direct = euclidean_distance(p(2.5, 2.5), p(8.5, 2.5))
        assert result.path_length > direct  # forced detour

    def test_start_within_goal_tolerance_is_a_trivial_path(self, map_factory) -> None:
        planner = RRTStarPlanner(RRTStarConfig(goal_tolerance=0.5))
        grid = OccupancyGrid(map_factory(5, 5))
        result = planner.plan(grid, p(2.2, 2.2), p(2.4, 2.2))
        assert result.success
        assert result.path == (p(2.2, 2.2), p(2.4, 2.2))
        assert result.cost == 0.0

    def test_no_simplification_keeps_tree_waypoints(self, map_factory) -> None:
        planner = RRTStarPlanner(
            RRTStarConfig(max_iterations=800, seed=1, simplify=False, step_size=0.3)
        )
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner.plan(grid, p(1.5, 1.5), p(1.5, 8.5))
        assert result.success
        assert_path_valid(grid, result.path)
        # Without shortcutting, a path built from ~0.3 m steps needs many
        # more waypoints than the straight-line minimum of 2.
        assert len(result.path) > 3


class TestRRTStarFailures:
    def test_no_path(self, map_factory, planner: RRTStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(10))))
        result = planner.plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert not result.success
        assert "no path" in result.failure_reason

    def test_start_outside_map(self, map_factory, planner: RRTStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5))
        result = planner.plan(grid, p(-1.0, 2.5), p(2.5, 2.5))
        assert not result.success
        assert "start is outside" in result.failure_reason

    def test_goal_outside_map(self, map_factory, planner: RRTStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5))
        result = planner.plan(grid, p(2.5, 2.5), p(7.0, 2.5))
        assert not result.success
        assert "goal is outside" in result.failure_reason

    def test_start_in_obstacle(self, map_factory, planner: RRTStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),)))
        result = planner.plan(grid, p(2.5, 2.5), p(4.5, 4.5))
        assert not result.success
        assert "start is inside an obstacle" in result.failure_reason

    def test_goal_in_obstacle(self, map_factory, planner: RRTStarPlanner) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),)))
        result = planner.plan(grid, p(0.5, 0.5), p(2.5, 2.5))
        assert not result.success
        assert "goal is inside an obstacle" in result.failure_reason


class TestRRTStarDeterminism:
    def test_identical_inputs_identical_paths(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(9))))
        config = RRTStarConfig(max_iterations=800, seed=7)
        first = RRTStarPlanner(config).plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        second = RRTStarPlanner(config).plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert first.success and second.success
        assert first.path == second.path
        assert first.cost == second.cost
        assert first.expanded_nodes == second.expanded_nodes

    def test_repeated_plan_calls_on_one_instance_are_also_identical(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10))
        planner = RRTStarPlanner(RRTStarConfig(max_iterations=500, seed=3))
        first = planner.plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        second = planner.plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert first.path == second.path

    def test_different_seeds_may_differ(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(9))))
        a = RRTStarPlanner(RRTStarConfig(max_iterations=800, seed=1)).plan(
            grid, p(2.5, 2.5), p(8.5, 2.5)
        )
        b = RRTStarPlanner(RRTStarConfig(max_iterations=800, seed=2)).plan(
            grid, p(2.5, 2.5), p(8.5, 2.5)
        )
        assert a.success and b.success
        # Not asserting inequality (two seeds could coincidentally find the
        # same shortcut path) — this documents that the seed is honoured
        # as an independent RNG stream, not a smoke test of divergence.
        assert_path_valid(grid, a.path)
        assert_path_valid(grid, b.path)


class TestRRTStarConfig:
    def test_rejects_non_positive_max_iterations(self) -> None:
        with pytest.raises(ValueError):
            RRTStarConfig(max_iterations=0)

    def test_rejects_goal_bias_outside_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            RRTStarConfig(goal_bias=1.5)
        with pytest.raises(ValueError):
            RRTStarConfig(goal_bias=-0.1)

    def test_rejects_non_positive_step_size(self) -> None:
        with pytest.raises(ValueError):
            RRTStarConfig(step_size=0.0)
