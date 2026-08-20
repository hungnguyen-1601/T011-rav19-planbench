"""What the map is like where the run went — E3.

Two of the explanation layer's most useful sentences are geometric:
*"the narrowest passage on this route is 0.68 m"* and *"this deployment
is twice as cluttered as the hall"*. Both are properties of the map, not
of any candidate, so they are measured once per route and shared by
every candidate that drove it.

**Measured, and only what can be measured.** The design sketch also
lists *topology* and *junction count*. Both need a Voronoi or skeleton
analysis that the note itself defers to a later item, and a coarse
stand-in would be worse than nothing: "corridor_with_side_aisles" is the
kind of label a reader takes as established fact, and one derived from a
guess would be an unearned one sitting in the same packet as measured
numbers. So this module returns clearance and clutter, and the fields
that need the harder analysis are simply absent until it exists.

**A passage width is measured across the route, not around a point.**
The first cut reported twice the distance to the nearest obstacle, which
is the diameter of the largest circle that fits — the corridor width
only where the route runs down the middle of it. A route hugging one
wall of an open hall came back as a narrow passage, and that number was
being handed to a detector that compares it against a robot's footprint.
So the measurement casts a ray each way along the route's normal and
adds the two distances: a cross-section, which is what the word "width"
means.

**Unknown space and the edge of the grid stop a ray.** Treating them as
free lets the measurement run out of the map and report a corridor as
open where nobody has mapped what is beside it.

**And a width from such a sample is kept apart from the others**, which
is the correction that matters. A ray stopped by unknown ground gives a
*lower* bound: the passage is at least this wide, and the unmapped side
may open into a hall. That direction can establish "wide enough" and it
cannot establish "too narrow" — ``0.3 m ≥ lower bound`` says nothing
about whether the true width clears 0.74 m. An earlier version called
the lower bound the safe direction and handed it to the check that
concludes a passage is impassable, which is the one conclusion it cannot
support. So ``narrowest_passage_m`` counts **only cross-sections closed
by obstacles on both sides**, and is ``None`` when no sample was; the
lower bound travels separately, for reading rather than for deciding.

**Clearance is from the robot's surface nowhere here.** These are map
distances, because the map has no robot in it. The comparison against a
robot's required clearance happens in the detector that needs it, where
the robot's radius is in scope.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_schemas.map import CellState, MapData


class MapFeatureRefusal(ValueError):
    """The map or route on hand cannot support the measurement."""


class RouteFeatures(BaseModel):
    """Geometry of the corridor a route runs through."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    #: The narrowest cross-section along the route — free space left of
    #: the heading plus free space right of it — counting **only**
    #: samples where an obstacle closed both rays. A width in the sense
    #: a robot can be compared against one.
    #:
    #: ``None`` when the route was never measured between two mapped
    #: obstacles. That is a refusal, not a missing convenience: the only
    #: number available then is a lower bound, and a lower bound cannot
    #: show a passage is too narrow.
    narrowest_passage_m: float | None = Field(default=None, ge=0.0)
    #: Where along the route that happened. ``None`` with the above.
    narrowest_at_progress_m: float | None = Field(default=None, ge=0.0)
    #: The narrowest cross-section over **every** measured sample, with
    #: coverage-limited ones counted at the distance their ray reached.
    #: At most the true width, so it can establish "wide enough" and
    #: never "too narrow". For reading, not for deciding.
    narrowest_lower_bound_m: float = Field(ge=0.0)
    #: Occupied cells over known cells, inside the corridor the route
    #: sweeps. Not over the whole map: a route down one clear aisle of a
    #: cluttered warehouse is not a cluttered route, and a figure that
    #: says it is would be describing the building.
    obstacle_density: float = Field(ge=0.0, le=1.0)
    #: How wide a band around the route the density was taken over.
    density_band_m: float = Field(gt=0.0)
    route_length_m: float = Field(ge=0.0)
    #: Route samples that fell outside the grid, or on unknown cells. A
    #: route measured over holes is a measurement with holes, and a
    #: reader is told rather than left to assume full coverage.
    unmeasured_samples: int = Field(ge=0)
    #: Samples whose cross-section ran into unknown space or off the edge
    #: of the grid before finding an obstacle. Their widths are lower
    #: bounds: a narrow reading here may be the map ending rather than a
    #: wall.
    samples_limited_by_coverage: int = Field(ge=0)

    @property
    def passage_width_is_measurable(self) -> bool:
        """Whether a clearance check may read :attr:`narrowest_passage_m`."""
        return self.narrowest_passage_m is not None

    @model_validator(mode="after")
    def _check(self) -> RouteFeatures:
        if (self.narrowest_passage_m is None) != (self.narrowest_at_progress_m is None):
            raise MapFeatureRefusal(
                "a narrowest passage and the place it was found travel together; one "
                "without the other is a width nobody can go and look at"
            )
        if (
            self.narrowest_at_progress_m is not None
            and self.narrowest_at_progress_m > self.route_length_m + 1e-9
        ):
            raise MapFeatureRefusal(
                f"narrowest point at {self.narrowest_at_progress_m} m on a route "
                f"{self.route_length_m} m long"
            )
        if (
            self.narrowest_passage_m is not None
            and self.narrowest_lower_bound_m > self.narrowest_passage_m + 1e-9
        ):
            raise MapFeatureRefusal(
                f"lower bound {self.narrowest_lower_bound_m} exceeds the measured width "
                f"{self.narrowest_passage_m}; a bound below a value is what makes it a bound"
            )
        return self


def measure_route(
    map_data: MapData,
    route: Sequence[tuple[float, float]],
    *,
    sample_spacing_m: float = 0.1,
    density_band_m: float = 2.0,
) -> RouteFeatures:
    """Clearance and clutter along one route.

    ``sample_spacing_m`` is the resolution of the answer, not of the
    map: sampling every 10 cm along the line finds a doorway a
    corner-to-corner segment would step straight over.
    """
    if len(route) < 2:
        raise MapFeatureRefusal("a route needs at least two points to have a length")
    if sample_spacing_m <= 0:
        raise MapFeatureRefusal(f"sample_spacing_m must be positive, got {sample_spacing_m}")
    if density_band_m <= 0:
        raise MapFeatureRefusal(f"density_band_m must be positive, got {density_band_m}")

    samples = list(_walk(route, sample_spacing_m))

    narrowest: float | None = None
    narrowest_at: float | None = None
    lower_bound = math.inf
    measured = 0
    unmeasured = 0
    limited = 0
    band_cells: set[int] = set()
    band_radius = max(1, int(round(density_band_m / map_data.resolution)))

    for index, (progress, point) in enumerate(samples):
        cell = _cell_of(map_data, *point)
        if cell is None:
            unmeasured += 1
            continue
        row, column = cell
        if map_data.cells[row * map_data.width + column] != CellState.FREE:
            unmeasured += 1
            continue

        measured += 1
        # Clutter is about where the route went, so every measured
        # sample counts — whether its cross-section happened to be
        # closed by walls is a fact about the *width*, not about how
        # built-up the surroundings are.
        band_cells.update(_band_indices(map_data, row, column, band_radius))

        width, bounded = _cross_section(map_data, point, _heading_at(samples, index))
        lower_bound = min(lower_bound, width)
        if not bounded:
            limited += 1
            continue
        if narrowest is None or width < narrowest:
            narrowest = width
            narrowest_at = progress

    if not measured:
        raise MapFeatureRefusal(
            "no sample of this route fell on a known free cell of the map; the route "
            "and the map are not describing the same place"
        )

    occupied = sum(1 for index in band_cells if map_data.cells[index] == CellState.OCCUPIED)
    known = sum(1 for index in band_cells if map_data.cells[index] != CellState.UNKNOWN)

    return RouteFeatures(
        narrowest_passage_m=narrowest,
        narrowest_at_progress_m=narrowest_at,
        narrowest_lower_bound_m=0.0 if lower_bound is math.inf else lower_bound,
        obstacle_density=(occupied / known) if known else 0.0,
        density_band_m=density_band_m,
        route_length_m=samples[-1][0] if samples else 0.0,
        unmeasured_samples=unmeasured,
        samples_limited_by_coverage=limited,
    )


def _heading_at(
    samples: Sequence[tuple[float, tuple[float, float]]], index: int
) -> tuple[float, float]:
    """Unit direction of travel at one sample, from its neighbours."""
    before = samples[max(0, index - 1)][1]
    after = samples[min(len(samples) - 1, index + 1)][1]
    dx, dy = after[0] - before[0], after[1] - before[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        return 1.0, 0.0
    return dx / length, dy / length


def _cross_section(
    map_data: MapData,
    point: tuple[float, float],
    heading: tuple[float, float],
    *,
    limit_m: float = 25.0,
) -> tuple[float, bool]:
    """Free width across the route here, and whether walls closed both ends.

    ``bounded`` is False when either ray left the grid or entered
    unknown space. The width is then a lower bound, and the caller says
    so rather than letting the edge of the map read as open floor.
    """
    normal = (-heading[1], heading[0])
    left, left_bounded = _ray(map_data, point, normal, limit_m)
    right, right_bounded = _ray(map_data, point, (-normal[0], -normal[1]), limit_m)
    return left + right, left_bounded and right_bounded


def _ray(
    map_data: MapData,
    origin: tuple[float, float],
    direction: tuple[float, float],
    limit_m: float,
) -> tuple[float, bool]:
    """How far along ``direction`` until something blocks the way."""
    step = map_data.resolution / 2
    travelled = 0.0
    while travelled < limit_m:
        travelled += step
        probe = (origin[0] + direction[0] * travelled, origin[1] + direction[1] * travelled)
        cell = _cell_of(map_data, *probe)
        if cell is None:
            return travelled, False
        value = map_data.cells[cell[0] * map_data.width + cell[1]]
        if value == CellState.OCCUPIED:
            return travelled, True
        if value == CellState.UNKNOWN:
            return travelled, False
    return limit_m, False


def _walk(
    route: Sequence[tuple[float, float]], spacing: float
) -> list[tuple[float, tuple[float, float]]]:
    """Points along the polyline, evenly spaced, with their arc length."""
    walked: list[tuple[float, tuple[float, float]]] = [(0.0, (route[0][0], route[0][1]))]
    travelled = 0.0
    for start, end in zip(route, route[1:], strict=False):
        segment = math.dist(start, end)
        if segment <= 0:
            continue
        # ``ceil``: with truncation a 0.95 m segment at 0.1 m spacing
        # became nine steps of 0.106 m, so the sampling was coarser than
        # the caller asked for — and a doorway between two samples is
        # exactly what this walk exists to catch.
        steps = max(1, math.ceil(segment / spacing))
        for step in range(1, steps + 1):
            ratio = step / steps
            walked.append(
                (
                    travelled + segment * ratio,
                    (
                        start[0] + (end[0] - start[0]) * ratio,
                        start[1] + (end[1] - start[1]) * ratio,
                    ),
                )
            )
        travelled += segment
    return walked


def _cell_of(map_data: MapData, x: float, y: float) -> tuple[int, int] | None:
    """The cell a world point falls in, or ``None`` when it is off the grid.

    ``floor``, not ``int``: truncation rounds toward zero, so a point
    10 cm *before* the origin landed in cell 0 and a route running just
    outside the map measured as though it were inside.

    Rotated origins cannot appear here — ``MapData`` refuses them at
    parse time — so this is a translation and a scale, nothing more.
    """
    column = math.floor((x - map_data.origin.x) / map_data.resolution)
    row = math.floor((y - map_data.origin.y) / map_data.resolution)
    if 0 <= row < map_data.height and 0 <= column < map_data.width:
        return row, column
    return None


def _band_indices(map_data: MapData, row: int, column: int, radius: int) -> list[int]:
    return [
        r * map_data.width + c
        for r in range(max(0, row - radius), min(map_data.height, row + radius + 1))
        for c in range(max(0, column - radius), min(map_data.width, column + radius + 1))
    ]
