"""E3 — measuring the corridor a route runs through.

The number that matters is the narrowest passage, because it is the one
a mechanism check compares a robot against. So these tests are mostly
about it being a *width* rather than half of one, being found even when
the doorway falls between two waypoints, and not being quoted for a
route the map has never heard of.
"""

from __future__ import annotations

import pytest

from planbench_explanation.map_features import MapFeatureRefusal, measure_route
from planbench_schemas.map import CellState, MapData


def grid(rows: list[str], *, resolution: float = 0.1) -> MapData:
    """A map from ASCII: ``#`` occupied, ``.`` free, ``?`` unknown.

    Row 0 of the list is row 0 of the grid, which sits at the origin and
    grows along +y — the same convention ``MapData`` documents.
    """
    cells: list[int] = []
    for row in rows:
        for character in row:
            cells.append(
                {
                    "#": CellState.OCCUPIED,
                    ".": CellState.FREE,
                    "?": CellState.UNKNOWN,
                }[character]
            )
    return MapData(
        name="fixture",
        width=len(rows[0]),
        height=len(rows),
        resolution=resolution,
        origin={"x": 0.0, "y": 0.0, "theta": 0.0},
        cells=tuple(cells),
    )


#: Two open halls joined by a doorway two cells wide. At 0.1 m per cell
#: the doorway is 0.2 m and the halls give at least 0.6 m — the doorway
#: has to be the *unique* narrowest point, or a test that finds it
#: proves nothing. An earlier version of this fixture had walls close
#: enough that the whole corridor tied with the door.
CORRIDOR = grid(
    [
        "####################",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "#########..#########",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "####################",
    ]
)


def test_the_narrowest_passage_is_a_width_not_half_of_one() -> None:
    """A passage is the room on *both* sides of the line through it.

    Reporting the distance to the nearest wall would give 0.1 m for a
    0.2 m doorway, and a robot compared against that number is compared
    against the wrong quantity.
    """
    features = measure_route(CORRIDOR, [(0.95, 0.35), (0.95, 1.05)], sample_spacing_m=0.02)

    assert features.narrowest_passage_m == pytest.approx(0.2, abs=0.06)


def test_the_doorway_is_found_even_when_it_falls_between_waypoints() -> None:
    """Two waypoints and a 0.7 m step would walk straight over it."""
    # One step across the whole route: the only samples are its two
    # ends, both of them in open floor.
    coarse = measure_route(CORRIDOR, [(0.95, 0.35), (0.95, 1.05)], sample_spacing_m=1.0)
    fine = measure_route(CORRIDOR, [(0.95, 0.35), (0.95, 1.05)], sample_spacing_m=0.02)

    # Coarse never lands between two walls, so it has no measured width
    # at all — the honest answer, rather than the width of the hall.
    assert coarse.narrowest_passage_m is None
    assert fine.narrowest_passage_m == pytest.approx(0.2, abs=0.06)
    # The doorway sits at y = 0.65, which is 0.30 m along a route that
    # starts at y = 0.35.
    assert fine.narrowest_at_progress_m == pytest.approx(0.30, abs=0.08)


def test_a_route_down_an_open_aisle_is_not_narrow() -> None:
    features = measure_route(CORRIDOR, [(0.2, 0.35), (1.8, 0.35)], sample_spacing_m=0.05)
    assert features.narrowest_passage_m > 0.3


def test_density_is_taken_around_the_route_not_over_the_building() -> None:
    """A clear aisle in a cluttered warehouse is a clear route.

    Measuring the whole map would describe the building and attach the
    number to the run.
    """
    cluttered = grid(
        [
            "....................",
            "....................",
            "####################",
            "####################",
            "####################",
        ]
    )

    near_the_wall = measure_route(cluttered, [(0.1, 0.15), (1.9, 0.15)], density_band_m=0.3)
    away_from_it = measure_route(cluttered, [(0.1, 0.05), (1.9, 0.05)], density_band_m=0.1)

    assert near_the_wall.obstacle_density > away_from_it.obstacle_density


def test_unknown_cells_are_counted_as_unmeasured_rather_than_as_free() -> None:
    """A route measured over holes is a measurement with holes."""
    foggy = grid(
        [
            "##########",
            "..????....",
            "##########",
        ]
    )

    features = measure_route(foggy, [(0.05, 0.15), (0.95, 0.15)], sample_spacing_m=0.05)

    assert features.unmeasured_samples > 0


def test_a_route_the_map_never_heard_of_is_refused() -> None:
    with pytest.raises(MapFeatureRefusal, match="not describing the same place"):
        measure_route(CORRIDOR, [(50.0, 50.0), (60.0, 60.0)])


def test_a_route_needs_two_points() -> None:
    with pytest.raises(MapFeatureRefusal):
        measure_route(CORRIDOR, [(0.2, 0.25)])


def test_the_measurement_is_deterministic() -> None:
    route = [(0.2, 0.35), (0.95, 0.35), (0.95, 1.05)]
    assert (
        measure_route(CORRIDOR, route).model_dump() == measure_route(CORRIDOR, route).model_dump()
    )


def test_the_narrowest_point_is_reported_where_it_is() -> None:
    features = measure_route(CORRIDOR, [(0.95, 0.35), (0.95, 1.05)], sample_spacing_m=0.02)
    assert 0.0 <= features.narrowest_at_progress_m <= features.route_length_m


# --------------------------------------------------------------------------
# What "width" has to mean
# --------------------------------------------------------------------------


def test_a_route_hugging_one_wall_of_an_open_hall_is_not_a_narrow_passage() -> None:
    """The reading the inscribed-circle version got wrong.

    Twice the distance to the nearest obstacle is the width of the
    corridor only where the route runs down the middle of it. Against a
    wall in an open hall it reports the wall, and that number was being
    handed to a check that compares it against a robot's footprint.
    """
    hall = grid(
        [
            "####################",
            "....................",
            "....................",
            "....................",
            "....................",
            "....................",
            "....................",
            "####################",
        ]
    )

    # 5 cm from the bottom wall, driving along it: nearest obstacle is
    # half a cell away, but the hall is 0.6 m across.
    features = measure_route(hall, [(0.2, 0.15), (1.8, 0.15)], sample_spacing_m=0.05)

    assert features.narrowest_passage_m == pytest.approx(0.6, abs=0.12)


def test_unknown_ground_stops_the_measurement_rather_than_reading_as_open() -> None:
    """A corridor whose far side nobody mapped is not a wide corridor."""
    half_mapped = grid(
        [
            "####################",
            "....................",
            "....................",
            "????????????????????",
            "????????????????????",
        ]
    )

    features = measure_route(half_mapped, [(0.2, 0.15), (1.8, 0.15)], sample_spacing_m=0.05)

    # No cross-section was closed on both sides, so there is no width to
    # hand a clearance check — only a lower bound, kept apart from it.
    assert features.samples_limited_by_coverage > 0
    assert features.narrowest_passage_m is None
    assert not features.passage_width_is_measurable
    assert features.narrowest_lower_bound_m < 0.5


def test_a_route_just_outside_the_map_is_not_quietly_pulled_inside() -> None:
    """``int()`` rounds toward zero, so x = −0.1 became column 0.

    A route the map does not cover measured as though it did, and came
    back with a confident width. Now the entirely-outside case refuses
    and the partly-outside case counts what it could not measure.
    """
    with pytest.raises(MapFeatureRefusal, match="not describing the same place"):
        measure_route(CORRIDOR, [(-0.4, 0.35), (-0.1, 0.35)], sample_spacing_m=0.05)

    straddling = measure_route(CORRIDOR, [(-0.4, 0.35), (0.4, 0.35)], sample_spacing_m=0.05)
    assert straddling.unmeasured_samples > 0
    assert straddling.narrowest_passage_m > 0


def test_the_walk_never_steps_further_than_the_spacing_asked_for() -> None:
    """``int(segment / spacing)`` made the real spacing coarser than
    declared, and the doorway between two samples is the thing this
    walk exists to catch."""
    from planbench_explanation.map_features import _walk

    walked = _walk([(0.0, 0.0), (0.95, 0.0)], 0.1)
    gaps = [second - first for (first, _), (second, _) in zip(walked, walked[1:], strict=False)]

    assert max(gaps) <= 0.1 + 1e-9


def test_a_lower_bound_never_becomes_the_number_a_clearance_check_reads() -> None:
    """ "At least 0.3 m" does not mean "narrower than 0.74 m".

    The unmapped side may open into a five-metre hall. A bound in this
    direction can establish *wide enough* and never *too narrow*, so the
    field a gap check reads is empty rather than optimistic-sounding.
    """
    open_to_the_unknown = grid(
        [
            "####################",
            "....................",
            "????????????????????",
        ]
    )

    features = measure_route(open_to_the_unknown, [(0.2, 0.15), (1.8, 0.15)], sample_spacing_m=0.05)

    assert features.narrowest_passage_m is None
    assert features.narrowest_lower_bound_m > 0
    # The bound is at most the truth, which is what makes it a bound.
    assert features.narrowest_lower_bound_m <= 0.3


def test_a_width_and_the_place_it_was_found_travel_together() -> None:
    from planbench_explanation.map_features import RouteFeatures

    with pytest.raises(Exception, match="travel together"):
        RouteFeatures(
            narrowest_passage_m=0.5,
            narrowest_at_progress_m=None,
            narrowest_lower_bound_m=0.4,
            obstacle_density=0.1,
            density_band_m=2.0,
            route_length_m=3.0,
            unmeasured_samples=0,
            samples_limited_by_coverage=0,
        )


def test_a_bound_above_the_value_it_bounds_is_refused() -> None:
    from planbench_explanation.map_features import RouteFeatures

    with pytest.raises(Exception, match="makes it a bound"):
        RouteFeatures(
            narrowest_passage_m=0.4,
            narrowest_at_progress_m=1.0,
            narrowest_lower_bound_m=0.9,
            obstacle_density=0.1,
            density_band_m=2.0,
            route_length_m=3.0,
            unmeasured_samples=0,
            samples_limited_by_coverage=0,
        )
