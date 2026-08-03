"""Tests for path utilities (length, line of sight, simplification)."""

from __future__ import annotations

import pytest

from planbench_planning import has_line_of_sight, path_length, simplify_path
from planbench_schemas.geometry import Point2D
from planbench_simulator.grid import OccupancyGrid


def p(x: float, y: float) -> Point2D:
    return Point2D(x=x, y=y)


class TestPathLength:
    def test_empty_and_single(self) -> None:
        assert path_length([]) == 0.0
        assert path_length([p(1.0, 1.0)]) == 0.0

    def test_polyline(self) -> None:
        assert path_length([p(0, 0), p(3, 0), p(3, 4)]) == pytest.approx(7.0)


class TestLineOfSight:
    def test_clear_segment(self, empty_grid: OccupancyGrid) -> None:
        assert has_line_of_sight(empty_grid, p(0.5, 0.5), p(4.5, 4.5))

    def test_blocked_segment(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=tuple((row, 2) for row in range(5))))
        assert not has_line_of_sight(grid, p(0.5, 2.5), p(4.5, 2.5))

    def test_segment_leaving_map_is_blocked(self, empty_grid: OccupancyGrid) -> None:
        assert not has_line_of_sight(empty_grid, p(0.5, 0.5), p(6.5, 0.5))

    def test_invalid_step_raises(self, empty_grid: OccupancyGrid) -> None:
        with pytest.raises(ValueError, match="step"):
            has_line_of_sight(empty_grid, p(0.5, 0.5), p(1.5, 0.5), step=0.0)


class TestSimplifyPath:
    def test_collinear_points_collapse(self, empty_grid: OccupancyGrid) -> None:
        path = [p(0.5, 0.5), p(1.5, 0.5), p(2.5, 0.5), p(3.5, 0.5)]
        simplified = simplify_path(empty_grid, path)
        assert simplified == (path[0], path[-1])

    def test_keeps_endpoints_and_validity(self, map_factory) -> None:
        # Wall col=2 with a gap at row 4: an L-shaped detour is required.
        grid = OccupancyGrid(map_factory(5, 5, occupied=tuple((row, 2) for row in range(4))))
        path = [p(0.5, 0.5), p(0.5, 4.5), p(2.5, 4.5), p(4.5, 4.5), p(4.5, 0.5)]
        simplified = simplify_path(grid, path)
        assert simplified[0] == path[0]
        assert simplified[-1] == path[-1]
        assert path_length(simplified) <= path_length(path) + 1e-9
        for a, b in zip(simplified, simplified[1:], strict=False):
            assert has_line_of_sight(grid, a, b)

    def test_short_paths_returned_unchanged(self, empty_grid: OccupancyGrid) -> None:
        short = [p(0.5, 0.5), p(1.5, 1.5)]
        assert simplify_path(empty_grid, short) == tuple(short)
