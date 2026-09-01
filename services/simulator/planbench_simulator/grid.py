"""Occupancy grid queries and obstacle inflation.

Wraps an immutable :class:`planbench_schemas.map.MapData`. All
operations are pure (no mutation, no global state) and deterministic.

Safety conventions (decisions D07 and D10 in
docs/reference/decision-log.md):
- World coordinates outside the map are reported as occupied.
- UNKNOWN cells count as occupied when ``unknown_as_occupied`` is True
  (the default).
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from scipy import ndimage

from planbench_schemas.geometry import EPS, Point2D, distance_point_to_aabb
from planbench_schemas.map import CellState, MapData
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle


class OccupancyGrid:
    """Read-only view over ``MapData`` with world/grid conversions.

    Optionally carries a **traversal layer**: a per-cell multiplier of
    ``1.0`` or more saying what a metre through that cell costs compared
    with a metre in the open. One is open floor; larger means "passable,
    and you will pay for it". It is *advice*, never a prohibition —
    :meth:`is_blocked_cell` ignores it entirely, and a planner that does
    not read it plans exactly as it always did.

    **The deployment's ``clearance_preference`` is already baked in**,
    and that is structural rather than tidy: it means no planner needs a
    λ of its own, so no candidate can buy a shorter route by caring less
    about clearance than its rivals were made to. Same enforcement as
    the safety envelope in phase 1 — there is no argument to abuse.

    Keeping this on the grid rather than in a parallel structure is
    deliberate too: they are two answers about the same cell, and a
    planner handed one without the other would be reasoning about a
    different map than the one it is refusing to enter.
    """

    def __init__(
        self,
        map_data: MapData,
        unknown_as_occupied: bool = True,
        traversal: np.ndarray | None = None,
    ) -> None:
        self._map = map_data
        self._unknown_as_occupied = unknown_as_occupied
        if traversal is not None:
            if traversal.shape != (map_data.height, map_data.width):
                raise ValueError(
                    f"traversal layer is {traversal.shape}, but the map is "
                    f"{(map_data.height, map_data.width)}"
                )
            if float(traversal.min()) < 1.0:
                raise ValueError(
                    "traversal multipliers below 1.0 would make hugging an obstacle "
                    f"cheaper than open floor; smallest was {float(traversal.min())!r}"
                )
        self._traversal = traversal

    @property
    def map_data(self) -> MapData:
        return self._map

    @property
    def traversal_layer(self) -> np.ndarray | None:
        """The raw layer, for callers building a derived grid from this one.

        Handed out rather than copied because the grid is read-only by
        convention and copying it per replan is a full array allocation
        on the hot path. A caller that mutates it is breaking the same
        rule as one that mutated ``map_data``.
        """
        return self._traversal

    @property
    def is_graded(self) -> bool:
        """True iff a traversal layer was built for this grid.

        Worth asking rather than assuming: a grid without one answers
        ``1.0`` everywhere, which is indistinguishable from open floor —
        and "no gradient here" and "this map has no gradient at all" are
        different facts about a plan.
        """
        return self._traversal is not None

    def traversal_at(self, row: int, col: int) -> float:
        """Cost multiplier for a metre through this cell; ``1.0`` if ungraded.

        One is the right answer for a grid with no layer: it makes every
        cost-aware planner degenerate *exactly* to its distance-only
        self, so a deployment can switch the gradient off without a
        second code path existing anywhere to rot.
        """
        if self._traversal is None:
            return 1.0
        self._check_index(row, col)
        return float(self._traversal[row, col])

    def traversal_at_world(self, x: float, y: float) -> float:
        """Multiplier at a world point; outside the map is the worst there is.

        Outside is already blocked, so nothing should be sampling it —
        but a planner that does must not be *rewarded* for leaving the
        map, which returning ``1.0`` would do.
        """
        cell = self.world_to_grid(x, y)
        if cell is None:
            return float(self._traversal.max()) if self._traversal is not None else 1.0
        return self.traversal_at(*cell)

    @property
    def width(self) -> int:
        return self._map.width

    @property
    def height(self) -> int:
        return self._map.height

    @property
    def resolution(self) -> float:
        return self._map.resolution

    @property
    def origin(self):
        return self._map.origin

    @property
    def unknown_as_occupied(self) -> bool:
        return self._unknown_as_occupied

    def world_to_grid(self, x: float, y: float) -> tuple[int, int] | None:
        """Return (row, col) of the cell containing the world point.

        Returns ``None`` when the point lies outside the map. Raises
        ``ValueError`` for NaN or infinite coordinates.
        """
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"coordinates must be finite, got ({x!r}, {y!r})")
        col = math.floor((x - self._map.origin.x) / self._map.resolution)
        row = math.floor((y - self._map.origin.y) / self._map.resolution)
        if 0 <= row < self._map.height and 0 <= col < self._map.width:
            return (row, col)
        return None

    def grid_to_world(self, row: int, col: int) -> Point2D:
        """Centre of cell (row, col) in world coordinates."""
        self._check_index(row, col)
        return Point2D(
            x=self._map.origin.x + (col + 0.5) * self._map.resolution,
            y=self._map.origin.y + (row + 0.5) * self._map.resolution,
        )

    def is_inside(self, x: float, y: float) -> bool:
        """True iff the world point falls inside the map bounds."""
        return self.world_to_grid(x, y) is not None

    def get_cell(self, row: int, col: int) -> CellState:
        """Cell state at (row, col); raises ``ValueError`` if out of range."""
        self._check_index(row, col)
        return CellState(self._map.cells[row * self._map.width + col])

    def is_blocked_cell(self, row: int, col: int) -> bool:
        """True iff the cell blocks the robot (OCCUPIED, or UNKNOWN per policy)."""
        state = self.get_cell(row, col)
        if state is CellState.OCCUPIED:
            return True
        return state is CellState.UNKNOWN and self._unknown_as_occupied

    def is_occupied(self, x: float, y: float) -> bool:
        """Occupancy at a world point; outside the map counts as occupied."""
        cell = self.world_to_grid(x, y)
        if cell is None:
            return True
        return self.is_blocked_cell(*cell)

    def inflate(self, radius: float) -> OccupancyGrid:
        """Return a new grid with OCCUPIED cells dilated by ``radius`` metres.

        Only OCCUPIED cells act as inflation sources. A cell (FREE or
        UNKNOWN) becomes OCCUPIED iff its centre lies within ``radius``
        of the centre of some source cell; UNKNOWN cells not covered by
        any source's inflation disk stay UNKNOWN. The original grid is
        never modified.

        This is a binary dilation of the occupied mask by a disk, and it
        is written as one because the nested-loop version was the single
        most expensive thing in an episode. Every replan re-inflates
        (the whole point of a replan is that something new is in the
        way), so the cost is paid tens of times per episode, and it
        scales as cells × disk area: 400,000 cells against a 0.54 m disk
        at 5 cm is ~140 million cell visits in Python. ``binary_dilation``
        does the same visits in C.

        The disk is symmetric, so there is no structuring-element origin
        subtlety, and ``binary_dilation`` treats out-of-bounds as unset,
        which matches the old loop iterating only over in-bounds sources.
        """
        if not math.isfinite(radius) or radius < 0:
            raise ValueError(f"radius must be finite and non-negative, got {radius!r}")
        if radius == 0:
            return OccupancyGrid(self._map, self._unknown_as_occupied)

        resolution = self._map.resolution
        reach = math.ceil(radius / resolution)
        span = np.arange(-reach, reach + 1)
        disk = np.hypot(span[:, None], span[None, :]) * resolution <= radius + EPS

        width, height = self._map.width, self._map.height
        cells = np.asarray(self._map.cells, dtype=np.int16).reshape(height, width)
        covered = ndimage.binary_dilation(cells == CellState.OCCUPIED.value, structure=disk)
        cells[covered] = CellState.OCCUPIED.value

        inflated_map = self._map.model_copy(update={"cells": tuple(cells.ravel().tolist())})
        return OccupancyGrid(inflated_map, self._unknown_as_occupied)

    def inflate_graded(self, hard_radius: float, ramp: float, preference: float) -> OccupancyGrid:
        r"""Block only the hard set; grade the caution beyond it as cost.

        **The problem this replaces.** Binary inflation answers one
        question — *may the robot be here* — with a number that is partly
        about the world and partly about the map file. On the shipped
        `sudden_stop` the planner's ring was 0.61 m, of which 0.35 m was
        ``√2 × resolution``: cell geometry, not physics. A robot standing
        at a spot its own collision test called legal was 0.30 m inside
        that ring, and every one of 55 replans reported "no path exists"
        — from a cell with **0 of 8** free neighbours.

        Grading dissolves it. The robot in that spot still has a way out;
        the way out is merely *expensive*. Nothing has to be un-forbidden
        for it to exist, which is why this makes the room-to-leave bubble
        unnecessary rather than smaller.

        **Quantisation is two-sided, and that is why no radius fixes
        this.** Distance here is centre to centre. The obstacle may be
        anywhere inside its cell and the robot anywhere inside its own,
        so a centre-to-centre distance *d* bounds the true distance only
        as ``d - √2 × resolution``. There is consequently **no inflation
        radius** for which "the controller says this pose is legal"
        implies "the planner's grid agrees" — the two disagree by up to a
        cell diagonal in either direction, whatever radius is chosen.
        Binary inflation has to pick a side; a gradient does not have to.

        So ``hard_radius`` blocks, and it should be
        :func:`~planbench_schemas.feasibility.hard_clearance` — the
        physics — while the quantisation slop moves into ``ramp``, where
        being wrong by a cell costs a little more rather than making a
        region uninhabitable.

        The penalty falls **linearly** from ``preference`` at the boundary
        to zero at ``hard_radius + ramp``, giving a multiplier between
        ``1 + preference`` and ``1``. Linear rather than exponential:
        Nav2's decay carries a rate constant somebody has to choose, and
        this project already refuses knobs that could be derived
        (``N_min``, the safety envelope, ``max_replans``). A straight ramp
        is fixed by its two endpoints, and both come from quantities the
        deployment already declares.

        ``preference`` is the deployment's ``clearance_preference``, and
        it is folded in **here** so that nothing downstream needs it. A
        planner receives a map that already prices caution; it cannot
        opt out of the price, and two candidates cannot be charged
        differently for the same metre.

        Cells inside the hard set are marked OCCUPIED and carry the
        maximum multiplier. It is never read — they are blocked — but
        leaving it at ``1.0`` would make the expensive band look like a
        wall with open floor behind it to anything reading the layer
        without the mask.
        """
        if not math.isfinite(hard_radius) or hard_radius < 0:
            raise ValueError(f"hard radius must be finite and non-negative, got {hard_radius!r}")
        if not math.isfinite(ramp) or ramp <= 0:
            raise ValueError(f"ramp must be finite and positive, got {ramp!r}")
        if not math.isfinite(preference) or preference < 0:
            raise ValueError(f"preference must be finite and non-negative, got {preference!r}")

        resolution = self._map.resolution
        width, height = self._map.width, self._map.height
        cells = np.asarray(self._map.cells, dtype=np.int16).reshape(height, width)
        sources = cells == CellState.OCCUPIED.value
        if not sources.any():
            return OccupancyGrid(self._map, self._unknown_as_occupied, np.ones((height, width)))

        # Distance in metres from each cell centre to the nearest occupied
        # cell centre. `distance_transform_edt` measures distance to the
        # nearest *zero*, so the mask is inverted.
        distance = ndimage.distance_transform_edt(~sources) * resolution

        blocked = distance <= hard_radius + EPS
        cells[blocked] = CellState.OCCUPIED.value
        nearness = np.clip((hard_radius + ramp - distance) / ramp, 0.0, 1.0)
        traversal = 1.0 + preference * nearness
        traversal[blocked] = 1.0 + preference

        graded_map = self._map.model_copy(update={"cells": tuple(cells.ravel().tolist())})
        return OccupancyGrid(graded_map, self._unknown_as_occupied, traversal)

    def _check_index(self, row: int, col: int) -> None:
        if not (0 <= row < self._map.height and 0 <= col < self._map.width):
            raise ValueError(
                f"cell index (row={row}, col={col}) out of range for "
                f"{self._map.height}x{self._map.width} grid"
            )


def rasterize_obstacles(
    map_data: MapData, obstacles: Iterable[CircleObstacle | RectangleObstacle]
) -> MapData:
    """Return a new ``MapData`` with shape obstacles burned in as OCCUPIED.

    A cell becomes OCCUPIED when the obstacle touches the cell's box
    (contact counts, consistent with the project collision rule).
    The input map is never modified.
    """
    width, height, resolution = map_data.width, map_data.height, map_data.resolution
    origin_x, origin_y = map_data.origin.x, map_data.origin.y
    cells = list(map_data.cells)

    def clamp_col(x: float) -> int:
        return min(width - 1, max(0, math.floor((x - origin_x) / resolution)))

    def clamp_row(y: float) -> int:
        return min(height - 1, max(0, math.floor((y - origin_y) / resolution)))

    for obstacle in obstacles:
        if isinstance(obstacle, CircleObstacle):
            min_x, max_x = obstacle.center.x - obstacle.radius, obstacle.center.x + obstacle.radius
            min_y, max_y = obstacle.center.y - obstacle.radius, obstacle.center.y + obstacle.radius
        elif isinstance(obstacle, RectangleObstacle):
            min_x, max_x = obstacle.min_x, obstacle.max_x
            min_y, max_y = obstacle.min_y, obstacle.max_y
        else:
            raise TypeError(f"unsupported obstacle type: {type(obstacle).__name__}")

        for row in range(clamp_row(min_y), clamp_row(max_y) + 1):
            cell_min_y = origin_y + row * resolution
            for col in range(clamp_col(min_x), clamp_col(max_x) + 1):
                cell_min_x = origin_x + col * resolution
                if isinstance(obstacle, CircleObstacle):
                    touches = (
                        distance_point_to_aabb(
                            obstacle.center.x,
                            obstacle.center.y,
                            cell_min_x,
                            cell_min_y,
                            cell_min_x + resolution,
                            cell_min_y + resolution,
                        )
                        <= obstacle.radius + EPS
                    )
                else:
                    touches = True  # the bounding-box range already is the overlap
                if touches:
                    cells[row * width + col] = CellState.OCCUPIED.value

    return map_data.model_copy(update={"cells": tuple(cells)})
