"""Tests for static collision detection and clearance.

Boundary-contact rule under test: contact counts as collision
(clearance <= EPS).
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from planbench_schemas.geometry import EPS, Point2D
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle
from planbench_simulator.collision import (
    clearance_to_circle,
    clearance_to_grid,
    clearance_to_obstacle,
    clearance_to_obstacles,
    clearance_to_rectangle,
    collides_with_grid,
    collides_with_obstacle,
)
from planbench_simulator.grid import OccupancyGrid


class TestCircleObstacle:
    def test_separated(self) -> None:
        obstacle = CircleObstacle(center=Point2D(x=10.0, y=0.0), radius=2.0)
        assert not collides_with_obstacle(Point2D(x=0.0, y=0.0), 1.0, obstacle)
        assert clearance_to_circle(Point2D(x=0.0, y=0.0), 1.0, obstacle) == pytest.approx(7.0)

    def test_overlapping(self) -> None:
        obstacle = CircleObstacle(center=Point2D(x=2.0, y=0.0), radius=2.0)
        assert collides_with_obstacle(Point2D(x=0.0, y=0.0), 1.0, obstacle)
        assert clearance_to_circle(Point2D(x=0.0, y=0.0), 1.0, obstacle) == pytest.approx(-1.0)

    def test_exact_tangency_is_collision(self) -> None:
        # Surfaces touch: distance 3.0 == robot 1.0 + obstacle 2.0.
        obstacle = CircleObstacle(center=Point2D(x=3.0, y=0.0), radius=2.0)
        assert collides_with_obstacle(Point2D(x=0.0, y=0.0), 1.0, obstacle)

    def test_separation_above_eps_is_not_collision(self) -> None:
        obstacle = CircleObstacle(center=Point2D(x=3.000001, y=0.0), radius=2.0)
        assert not collides_with_obstacle(Point2D(x=0.0, y=0.0), 1.0, obstacle)

    def test_separation_below_eps_is_collision(self) -> None:
        obstacle = CircleObstacle(center=Point2D(x=3.0 + EPS / 2, y=0.0), radius=2.0)
        assert collides_with_obstacle(Point2D(x=0.0, y=0.0), 1.0, obstacle)


class TestRectangleObstacle:
    RECT = RectangleObstacle(min_x=1.0, min_y=-1.0, max_x=2.0, max_y=1.0)

    def test_separated_from_edge(self) -> None:
        assert clearance_to_rectangle(Point2D(x=0.0, y=0.0), 0.5, self.RECT) == pytest.approx(0.5)
        assert not collides_with_obstacle(Point2D(x=0.0, y=0.0), 0.5, self.RECT)

    def test_tangent_to_edge_is_collision(self) -> None:
        assert collides_with_obstacle(Point2D(x=0.0, y=0.0), 1.0, self.RECT)

    def test_near_corner_uses_euclidean_distance(self) -> None:
        # Corner (1, 1); centre at (0, 2) -> distance sqrt(2).
        clearance = clearance_to_rectangle(Point2D(x=0.0, y=2.0), 0.5, self.RECT)
        assert clearance == pytest.approx(math.sqrt(2.0) - 0.5)
        assert not collides_with_obstacle(Point2D(x=0.0, y=2.0), 0.5, self.RECT)
        assert collides_with_obstacle(Point2D(x=0.0, y=2.0), 1.5, self.RECT)

    def test_centre_inside_rectangle(self) -> None:
        clearance = clearance_to_rectangle(Point2D(x=1.5, y=0.0), 0.3, self.RECT)
        assert clearance == pytest.approx(-0.3)
        assert collides_with_obstacle(Point2D(x=1.5, y=0.0), 0.3, self.RECT)

    @pytest.mark.parametrize(
        ("min_x", "min_y", "max_x", "max_y"),
        [(2.0, 0.0, 1.0, 1.0), (0.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0)],
    )
    def test_invalid_extent_rejected(
        self, min_x: float, min_y: float, max_x: float, max_y: float
    ) -> None:
        with pytest.raises(ValidationError, match="positive extent"):
            RectangleObstacle(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    def test_dispatch_rejects_unknown_type(self) -> None:
        with pytest.raises(TypeError, match="unsupported obstacle type"):
            clearance_to_obstacle(Point2D(x=0.0, y=0.0), 1.0, "not-an-obstacle")  # type: ignore[arg-type]


class TestGridCollision:
    def test_free_space_no_collision(self, empty_grid: OccupancyGrid) -> None:
        assert not collides_with_grid(Point2D(x=2.5, y=2.5), 0.5, empty_grid)

    def test_overlapping_occupied_cell(self, mixed_grid: OccupancyGrid) -> None:
        # OCCUPIED cell spans [2, 3] x [2, 3].
        assert collides_with_grid(Point2D(x=2.5, y=2.5), 0.3, mixed_grid)
        assert collides_with_grid(Point2D(x=1.8, y=2.5), 0.5, mixed_grid)

    def test_tangent_to_cell_face_is_collision(self, mixed_grid: OccupancyGrid) -> None:
        # Centre at x=1.5, cell face at x=2.0, radius 0.5 -> exact contact.
        assert collides_with_grid(Point2D(x=1.5, y=2.5), 0.5, mixed_grid)

    def test_clear_of_cell_no_collision(self, mixed_grid: OccupancyGrid) -> None:
        assert not collides_with_grid(Point2D(x=1.4, y=2.5), 0.5, mixed_grid)

    def test_robot_reaching_map_edge_is_collision(self, empty_grid: OccupancyGrid) -> None:
        # Outside-of-map counts as obstacle: boundary at x=0.
        assert collides_with_grid(Point2D(x=0.5, y=2.5), 0.5, empty_grid)
        assert not collides_with_grid(Point2D(x=0.6, y=2.5), 0.5, empty_grid)

    def test_unknown_cell_blocks_by_default(self, map_factory) -> None:
        # UNKNOWN cell at (row 0, col 4) spans [4, 5] x [0, 1].
        grid_default = OccupancyGrid(map_factory(5, 5, unknown=((0, 4),)))
        grid_traversable = OccupancyGrid(
            map_factory(5, 5, unknown=((0, 4),)), unknown_as_occupied=False
        )
        centre = Point2D(x=3.8, y=0.5)
        assert collides_with_grid(centre, 0.3, grid_default)
        assert not collides_with_grid(centre, 0.3, grid_traversable)

    @pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
    def test_invalid_radius_raises(self, empty_grid: OccupancyGrid, bad: float) -> None:
        with pytest.raises(ValueError, match="radius"):
            collides_with_grid(Point2D(x=2.5, y=2.5), bad, empty_grid)


class TestClearance:
    def test_grid_clearance_in_empty_map_is_boundary_distance(
        self, empty_grid: OccupancyGrid
    ) -> None:
        clearance = clearance_to_grid(Point2D(x=2.5, y=2.5), 0.5, empty_grid)
        assert clearance == pytest.approx(2.0)  # 2.5 to boundary minus radius 0.5

    def test_grid_clearance_to_occupied_cell(self, mixed_grid: OccupancyGrid) -> None:
        # Centre (2.5, 1.5): occupied cell face at y=2.0 -> distance 0.5;
        # boundary distance 1.5; nearest is the cell.
        clearance = clearance_to_grid(Point2D(x=2.5, y=1.5), 0.2, mixed_grid)
        assert clearance == pytest.approx(0.3)

    def test_grid_clearance_negative_when_penetrating(self, mixed_grid: OccupancyGrid) -> None:
        clearance = clearance_to_grid(Point2D(x=2.5, y=2.5), 0.3, mixed_grid)
        assert clearance == pytest.approx(-0.3)

    def test_grid_clearance_ignores_unknown_when_flag_disabled(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(5, 5, unknown=((2, 2),)), unknown_as_occupied=False)
        clearance = clearance_to_grid(Point2D(x=2.5, y=2.5), 0.2, grid)
        assert clearance == pytest.approx(2.3)  # only the boundary remains

    def test_min_over_mixed_obstacles_and_grid(self, empty_grid: OccupancyGrid) -> None:
        centre = Point2D(x=2.5, y=2.5)
        circle = CircleObstacle(center=Point2D(x=2.5, y=4.0), radius=0.5)  # clearance 0.8
        rect = RectangleObstacle(min_x=4.0, min_y=2.0, max_x=4.5, max_y=3.0)  # clearance 1.3
        clearance = clearance_to_obstacles(centre, 0.2, [circle, rect], grid=empty_grid)
        assert clearance == pytest.approx(0.8)

    def test_empty_obstacles_without_grid_is_infinite(self) -> None:
        assert clearance_to_obstacles(Point2D(x=0.0, y=0.0), 0.5, []) == math.inf
