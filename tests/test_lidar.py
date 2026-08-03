"""Tests for the simulated LiDAR (grid ray casting)."""

from __future__ import annotations

import math

import pytest

from planbench_schemas.geometry import Pose2D
from planbench_schemas.sensor import LidarConfig
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.lidar import cast_ray, scan


class TestCastRay:
    def test_empty_map_returns_max_range(self, empty_grid: OccupancyGrid) -> None:
        # No obstacle: the ray exits the map -> max_range by convention.
        assert cast_ray(empty_grid, 2.5, 2.5, 0.0, 10.0) == 10.0
        assert cast_ray(empty_grid, 2.5, 2.5, math.pi, 10.0) == 10.0

    def test_hits_wall_at_face_distance(self, map_factory) -> None:
        # Wall column col=4 spans x in [4, 5]; robot at x=2.5 -> distance 1.5.
        grid = OccupancyGrid(map_factory(5, 5, occupied=tuple((row, 4) for row in range(5))))
        assert cast_ray(grid, 2.5, 2.5, 0.0, 10.0) == pytest.approx(1.5, abs=1e-9)

    def test_hits_wall_in_negative_direction(self, map_factory) -> None:
        # Wall column col=0 spans x in [0, 1]; robot at x=2.5 -> distance 1.5.
        grid = OccupancyGrid(map_factory(5, 5, occupied=tuple((row, 0) for row in range(5))))
        assert cast_ray(grid, 2.5, 2.5, math.pi, 10.0) == pytest.approx(1.5, abs=1e-9)

    def test_vertical_ray(self, map_factory) -> None:
        # Wall row=4 spans y in [4, 5]; robot at y=2.5 -> distance 1.5 upward.
        grid = OccupancyGrid(map_factory(5, 5, occupied=tuple((4, col) for col in range(5))))
        assert cast_ray(grid, 2.5, 2.5, math.pi / 2, 10.0) == pytest.approx(1.5, abs=1e-9)

    def test_diagonal_ray(self, map_factory) -> None:
        # Occupied cell (3, 3) spans [3, 4]x[3, 4]; from (2.5, 2.5) at 45deg
        # the ray enters that cell at distance sqrt(2)/2.
        grid = OccupancyGrid(map_factory(5, 5, occupied=((3, 3),)))
        expected = math.sqrt(2.0) / 2.0
        assert cast_ray(grid, 2.5, 2.5, math.pi / 4, 10.0) == pytest.approx(expected, abs=1e-9)

    def test_range_clamped(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=tuple((row, 4) for row in range(5))))
        assert cast_ray(grid, 2.5, 2.5, 0.0, 1.0) == 1.0  # wall is at 1.5 > max_range

    def test_origin_in_blocked_cell_returns_zero(self, mixed_grid: OccupancyGrid) -> None:
        assert cast_ray(mixed_grid, 2.5, 2.5, 0.0, 10.0) == 0.0

    def test_unknown_respects_policy(self, map_factory) -> None:
        blocking = OccupancyGrid(map_factory(5, 5, unknown=((2, 4),)))
        transparent = OccupancyGrid(map_factory(5, 5, unknown=((2, 4),)), unknown_as_occupied=False)
        # UNKNOWN cell (2, 4) spans x in [4, 5] at the robot's row.
        assert cast_ray(blocking, 2.5, 2.5, 0.0, 10.0) == pytest.approx(1.5, abs=1e-9)
        assert cast_ray(transparent, 2.5, 2.5, 0.0, 10.0) == 10.0

    def test_origin_outside_map_raises(self, empty_grid: OccupancyGrid) -> None:
        with pytest.raises(ValueError, match="outside the map"):
            cast_ray(empty_grid, -1.0, 2.5, 0.0, 10.0)

    @pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
    def test_invalid_max_range_raises(self, empty_grid: OccupancyGrid, bad: float) -> None:
        with pytest.raises(ValueError, match="max_range"):
            cast_ray(empty_grid, 2.5, 2.5, 0.0, bad)


class TestScan:
    def test_ray_count_and_determinism(self, empty_grid: OccupancyGrid) -> None:
        config = LidarConfig(num_rays=8, max_range=10.0)
        pose = Pose2D(x=2.5, y=2.5, theta=0.3)
        first = scan(empty_grid, pose, config)
        second = scan(empty_grid, pose, config)
        assert len(first) == 8
        assert first == second

    def test_angles_relative_to_heading(self, map_factory) -> None:
        # Wall to the +y side; robot heading +y -> the centre ray (relative
        # angle -span/2 + (num_rays/2)*increment = 0) sees the wall.
        grid = OccupancyGrid(map_factory(5, 5, occupied=tuple((4, col) for col in range(5))))
        config = LidarConfig(num_rays=4, max_range=10.0)  # relative angles -pi, -pi/2, 0, pi/2
        pose = Pose2D(x=2.5, y=2.5, theta=math.pi / 2)
        ranges = scan(grid, pose, config)
        assert ranges[2] == pytest.approx(1.5, abs=1e-9)  # relative 0 -> absolute +y
        assert ranges[0] == 10.0  # relative -pi -> absolute -y, no wall
