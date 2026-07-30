"""Shared fixtures for PlanBench Phase 1A tests."""

from __future__ import annotations

import pytest

from planbench_schemas.geometry import Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.robot import RobotConfig
from planbench_simulator.grid import OccupancyGrid


def _make_map(
    width: int,
    height: int,
    resolution: float = 1.0,
    occupied: tuple[tuple[int, int], ...] = (),
    unknown: tuple[tuple[int, int], ...] = (),
    origin: Pose2D | None = None,
    name: str = "test-map",
) -> MapData:
    if origin is None:
        origin = Pose2D(x=0.0, y=0.0, theta=0.0)
    cells = [CellState.FREE.value] * (width * height)
    for row, col in occupied:
        cells[row * width + col] = CellState.OCCUPIED.value
    for row, col in unknown:
        cells[row * width + col] = CellState.UNKNOWN.value
    return MapData(
        name=name,
        width=width,
        height=height,
        resolution=resolution,
        origin=origin,
        cells=tuple(cells),
    )


def _make_bordered_map(
    width: int,
    height: int,
    resolution: float = 1.0,
    occupied: tuple[tuple[int, int], ...] = (),
    name: str = "bordered-test-map",
) -> MapData:
    """Map with a one-cell wall around the border plus extra occupied cells."""
    border = [(0, col) for col in range(width)] + [(height - 1, col) for col in range(width)]
    border += [(row, 0) for row in range(height)] + [(row, width - 1) for row in range(height)]
    return _make_map(
        width, height, resolution=resolution, occupied=tuple(border) + tuple(occupied), name=name
    )


@pytest.fixture
def map_factory():
    """Build small test maps: map_factory(width, height, occupied=[(row, col)], ...)."""
    return _make_map


@pytest.fixture
def bordered_map_factory():
    """Like map_factory but with border walls (needed for episode runs)."""
    return _make_bordered_map


@pytest.fixture
def empty_grid():
    """5x5 free grid, resolution 1.0 m, origin (0, 0): world x, y in [0, 5)."""
    return OccupancyGrid(_make_map(5, 5))


@pytest.fixture
def mixed_grid():
    """5x5 grid with OCCUPIED at (row 2, col 2) and UNKNOWN at (row 0, col 4)."""
    return OccupancyGrid(_make_map(5, 5, occupied=((2, 2),), unknown=((0, 4),)))


@pytest.fixture
def robot_config():
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=2.0,
    )
