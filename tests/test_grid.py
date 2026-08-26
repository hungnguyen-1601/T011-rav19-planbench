"""Tests for the MapData schema and OccupancyGrid."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from planbench_schemas.geometry import EPS, Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_simulator.grid import OccupancyGrid


class TestMapDataValidation:
    def test_valid_map(self, map_factory) -> None:
        map_data = map_factory(3, 2)
        assert map_data.width == 3
        assert map_data.height == 2
        assert len(map_data.cells) == 6

    def test_cells_length_mismatch(self) -> None:
        with pytest.raises(ValidationError, match="expected width"):
            MapData(
                name="broken",
                width=3,
                height=2,
                resolution=1.0,
                origin=Pose2D(x=0.0, y=0.0),
                cells=(0, 0, 0),
            )

    def test_invalid_cell_value(self) -> None:
        with pytest.raises(ValidationError, match="invalid values"):
            MapData(
                name="broken",
                width=2,
                height=2,
                resolution=1.0,
                origin=Pose2D(x=0.0, y=0.0),
                cells=(0, 0, 0, 5),
            )

    @pytest.mark.parametrize("bad_resolution", [0.0, -0.5])
    def test_resolution_must_be_positive(self, map_factory, bad_resolution: float) -> None:
        with pytest.raises(ValidationError):
            map_factory(2, 2, resolution=bad_resolution)

    @pytest.mark.parametrize("bad_size", [0, -1])
    def test_dimensions_must_be_positive(self, map_factory, bad_size: int) -> None:
        with pytest.raises(ValidationError):
            map_factory(bad_size, 2)

    def test_rotated_origin_rejected(self, map_factory) -> None:
        with pytest.raises(ValidationError, match="Rotated map origins"):
            map_factory(2, 2, origin=Pose2D(x=0.0, y=0.0, theta=0.1))

    def test_origin_theta_within_eps_accepted(self, map_factory) -> None:
        map_data = map_factory(2, 2, origin=Pose2D(x=0.0, y=0.0, theta=1e-12))
        assert map_data.origin.theta == 1e-12


class TestChecksum:
    def test_stable_for_identical_maps(self, map_factory) -> None:
        a = map_factory(4, 4, occupied=((1, 1),))
        b = map_factory(4, 4, occupied=((1, 1),))
        assert a.checksum() == b.checksum()

    def test_changes_when_cell_changes(self, map_factory) -> None:
        a = map_factory(4, 4, occupied=((1, 1),))
        b = map_factory(4, 4, occupied=((1, 2),))
        assert a.checksum() != b.checksum()

    def test_changes_when_name_changes(self, map_factory) -> None:
        a = map_factory(4, 4, name="a")
        b = map_factory(4, 4, name="b")
        assert a.checksum() != b.checksum()


class TestWorldGridConversion:
    def test_world_to_grid_basic(self, empty_grid: OccupancyGrid) -> None:
        assert empty_grid.world_to_grid(0.5, 0.5) == (0, 0)
        assert empty_grid.world_to_grid(4.999, 4.999) == (4, 4)
        assert empty_grid.world_to_grid(2.0, 3.0) == (3, 2)  # (row, col)

    def test_world_to_grid_outside_returns_none(self, empty_grid: OccupancyGrid) -> None:
        assert empty_grid.world_to_grid(5.0, 2.0) is None
        assert empty_grid.world_to_grid(-0.001, 2.0) is None
        assert empty_grid.world_to_grid(2.0, 5.0) is None

    def test_world_to_grid_with_offset_origin(self, map_factory) -> None:
        grid = OccupancyGrid(
            map_factory(4, 3, resolution=0.5, origin=Pose2D(x=-1.0, y=-2.0, theta=0.0))
        )
        assert grid.world_to_grid(-1.0, -2.0) == (0, 0)
        assert grid.world_to_grid(0.9, -0.6) == (2, 3)
        assert grid.world_to_grid(1.0, -1.0) is None  # x = 1.0 is just past the last column

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_world_to_grid_rejects_non_finite(self, empty_grid: OccupancyGrid, bad: float) -> None:
        with pytest.raises(ValueError, match="finite"):
            empty_grid.world_to_grid(bad, 0.0)

    def test_grid_to_world_returns_cell_centre(self, empty_grid: OccupancyGrid) -> None:
        centre = empty_grid.grid_to_world(0, 0)
        assert (centre.x, centre.y) == (0.5, 0.5)
        centre = empty_grid.grid_to_world(3, 1)
        assert (centre.x, centre.y) == (1.5, 3.5)

    def test_round_trip_all_cells(self, empty_grid: OccupancyGrid) -> None:
        for row in range(empty_grid.height):
            for col in range(empty_grid.width):
                centre = empty_grid.grid_to_world(row, col)
                assert empty_grid.world_to_grid(centre.x, centre.y) == (row, col)

    @pytest.mark.parametrize(("row", "col"), [(-1, 0), (0, -1), (5, 0), (0, 5)])
    def test_grid_to_world_out_of_range_raises(
        self, empty_grid: OccupancyGrid, row: int, col: int
    ) -> None:
        with pytest.raises(ValueError, match="out of range"):
            empty_grid.grid_to_world(row, col)

    def test_is_inside(self, empty_grid: OccupancyGrid) -> None:
        assert empty_grid.is_inside(2.5, 2.5)
        assert not empty_grid.is_inside(5.5, 2.5)


class TestOccupancyQueries:
    def test_get_cell(self, mixed_grid: OccupancyGrid) -> None:
        assert mixed_grid.get_cell(2, 2) is CellState.OCCUPIED
        assert mixed_grid.get_cell(0, 4) is CellState.UNKNOWN
        assert mixed_grid.get_cell(0, 0) is CellState.FREE

    def test_get_cell_out_of_range_raises(self, mixed_grid: OccupancyGrid) -> None:
        with pytest.raises(ValueError, match="out of range"):
            mixed_grid.get_cell(5, 0)

    def test_is_occupied_semantics(self, mixed_grid: OccupancyGrid) -> None:
        assert mixed_grid.is_occupied(2.5, 2.5)  # OCCUPIED cell
        assert not mixed_grid.is_occupied(0.5, 0.5)  # FREE cell
        assert mixed_grid.is_occupied(4.5, 0.5)  # UNKNOWN, default unknown_as_occupied=True
        assert mixed_grid.is_occupied(10.0, 10.0)  # outside the map

    def test_unknown_not_occupied_when_flag_disabled(self, map_factory) -> None:
        grid = OccupancyGrid(
            map_factory(5, 5, occupied=((2, 2),), unknown=((0, 4),)),
            unknown_as_occupied=False,
        )
        assert not grid.is_occupied(4.5, 0.5)  # UNKNOWN now traversable
        assert grid.is_occupied(2.5, 2.5)  # OCCUPIED unaffected

    def test_unknown_as_occupied_property(self, empty_grid: OccupancyGrid, map_factory) -> None:
        assert empty_grid.unknown_as_occupied is True
        relaxed = OccupancyGrid(map_factory(2, 2), unknown_as_occupied=False)
        assert relaxed.unknown_as_occupied is False


class TestInflation:
    def test_radius_one_gives_cross_shape(self, map_factory) -> None:
        inflated = OccupancyGrid(map_factory(7, 7, occupied=((3, 3),))).inflate(1.0)
        expected_occupied = {(3, 3), (2, 3), (4, 3), (3, 2), (3, 4)}
        for row in range(7):
            for col in range(7):
                expected = CellState.OCCUPIED if (row, col) in expected_occupied else CellState.FREE
                assert inflated.get_cell(row, col) is expected, (row, col)

    def test_radius_covering_diagonals_gives_block(self, map_factory) -> None:
        inflated = OccupancyGrid(map_factory(7, 7, occupied=((3, 3),))).inflate(1.5)
        expected_occupied = {
            (row, col) for row in range(2, 5) for col in range(2, 5)
        }  # 3x3 block: diagonal centre distance sqrt(2) <= 1.5
        for row in range(7):
            for col in range(7):
                expected = CellState.OCCUPIED if (row, col) in expected_occupied else CellState.FREE
                assert inflated.get_cell(row, col) is expected, (row, col)

    def test_unknown_is_not_an_inflation_source(self, map_factory) -> None:
        inflated = OccupancyGrid(map_factory(5, 5, unknown=((2, 2),))).inflate(1.0)
        assert inflated.get_cell(2, 2) is CellState.UNKNOWN
        for row, col in ((1, 2), (3, 2), (2, 1), (2, 3)):
            assert inflated.get_cell(row, col) is CellState.FREE

    def test_unknown_covered_by_occupied_inflation_becomes_occupied(self, map_factory) -> None:
        inflated = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),), unknown=((2, 3),))).inflate(
            1.0
        )
        assert inflated.get_cell(2, 3) is CellState.OCCUPIED

    def test_unknown_outside_inflation_reach_stays_unknown(self, map_factory) -> None:
        inflated = OccupancyGrid(map_factory(5, 5, occupied=((0, 0),), unknown=((4, 4),))).inflate(
            1.0
        )
        assert inflated.get_cell(4, 4) is CellState.UNKNOWN

    def test_original_grid_is_not_mutated(self, map_factory) -> None:
        original_map = map_factory(5, 5, occupied=((2, 2),))
        grid = OccupancyGrid(original_map)
        grid.inflate(2.0)
        assert grid.map_data.cells == original_map.cells
        assert grid.get_cell(2, 3) is CellState.FREE

    def test_zero_radius_is_identity(self, mixed_grid: OccupancyGrid) -> None:
        inflated = mixed_grid.inflate(0.0)
        assert inflated.map_data.cells == mixed_grid.map_data.cells

    def test_inflation_clipped_at_map_edges(self, map_factory) -> None:
        inflated = OccupancyGrid(map_factory(3, 3, occupied=((0, 0),))).inflate(1.0)
        assert inflated.get_cell(0, 1) is CellState.OCCUPIED
        assert inflated.get_cell(1, 0) is CellState.OCCUPIED
        assert inflated.get_cell(2, 2) is CellState.FREE

    @pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf])
    def test_invalid_radius_raises(self, empty_grid: OccupancyGrid, bad: float) -> None:
        with pytest.raises(ValueError, match="radius"):
            empty_grid.inflate(bad)

    def test_inflated_map_checksum_differs(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),)))
        inflated = grid.inflate(1.0)
        assert inflated.map_data.checksum() != grid.map_data.checksum()


def _inflate_by_definition(map_data: MapData, radius: float) -> tuple[int, ...]:
    """``inflate`` written the way the docstring says, cell by cell.

    Deliberately the slow, obvious version: mark every cell within
    ``radius`` of an OCCUPIED cell's centre. It is here to be compared
    against, not to be used.
    """
    reach = math.ceil(radius / map_data.resolution)
    offsets = [
        (dr, dc)
        for dr in range(-reach, reach + 1)
        for dc in range(-reach, reach + 1)
        if math.hypot(dr, dc) * map_data.resolution <= radius + EPS
    ]
    width, height = map_data.width, map_data.height
    cells = list(map_data.cells)
    for row in range(height):
        for col in range(width):
            if map_data.cells[row * width + col] != CellState.OCCUPIED:
                continue
            for dr, dc in offsets:
                r, c = row + dr, col + dc
                if 0 <= r < height and 0 <= c < width:
                    cells[r * width + c] = CellState.OCCUPIED.value
    return tuple(cells)


class TestInflationMatchesItsDefinition:
    """``inflate`` is a binary dilation for speed — 5.5 s to 35 ms on the
    800x500 reference warehouse, which is most of an episode's cost since
    every replan re-inflates.

    Speed is the only reason it is written that way, so the thing worth
    testing is that it did not buy the speed with a changed answer. These
    compare it against the nested-loop reading of the docstring on the
    cases where a dilation could plausibly differ: a disk that is not a
    square, the map border, and UNKNOWN cells, which are not inflation
    sources but can be inflation targets.
    """

    @pytest.mark.parametrize("radius", [0.5, 1.0, 1.5, 2.0, 3.7])
    def test_it_agrees_on_a_cluttered_grid(self, map_factory, radius: float) -> None:
        map_data = map_factory(
            13,
            11,
            occupied=((0, 0), (2, 5), (3, 6), (7, 1), (10, 12), (5, 5)),
            unknown=((2, 6), (8, 2), (0, 12), (10, 0)),
        )
        assert OccupancyGrid(map_data).inflate(radius).map_data.cells == _inflate_by_definition(
            map_data, radius
        )

    def test_it_agrees_when_the_disk_overruns_every_edge(self, map_factory) -> None:
        """Out-of-bounds is the one place a dilation could differ by
        convention: the loop simply never writes there."""
        map_data = map_factory(4, 4, occupied=((0, 0), (3, 3)))
        assert OccupancyGrid(map_data).inflate(9.0).map_data.cells == _inflate_by_definition(
            map_data, 9.0
        )
