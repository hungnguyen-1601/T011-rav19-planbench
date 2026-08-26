"""Path post-processing utilities: length, line of sight, simplification.

All functions are pure and deterministic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from planbench_schemas.geometry import EPS, Point2D, euclidean_distance
from planbench_simulator.grid import OccupancyGrid


def path_length(path: Sequence[Point2D]) -> float:
    """Total Euclidean length of a polyline, in metres."""
    return sum(euclidean_distance(path[i], path[i + 1]) for i in range(len(path) - 1))


def has_line_of_sight(
    grid: OccupancyGrid, a: Point2D, b: Point2D, step: float | None = None
) -> bool:
    """True iff the segment a-b crosses no blocked cell.

    Samples the segment every ``step`` metres (default: resolution / 4).
    Points outside the map count as blocked. On an inflated grid this
    approximates a swept-circle check for the robot.
    """
    if step is None:
        step = grid.resolution / 4.0
    if step <= 0:
        raise ValueError(f"step must be positive, got {step!r}")
    distance = euclidean_distance(a, b)
    samples = max(1, math.ceil(distance / step))
    for i in range(samples + 1):
        t = i / samples
        x = a.x + (b.x - a.x) * t
        y = a.y + (b.y - a.y) * t
        if grid.is_occupied(x, y):
            return False
    return True


def segment_cost(grid: OccupancyGrid, a: Point2D, b: Point2D, step: float | None = None) -> float:
    r"""Length of a-b weighted by the grid's traversal multipliers.

    The line integral of "what a metre costs here" along the segment,
    approximated by sampling at the same stride the visibility check
    uses. On an ungraded grid every multiplier is ``1.0`` and this is
    exactly :func:`euclidean_distance`.

    Sampled rather than solved because the multiplier is piecewise
    constant per cell and the exact integral would mean walking the
    segment's cell traversal (an Amanatides–Woo march). The stride is a
    quarter of a cell, so the error is bounded by a quarter cell's worth
    of one multiplier — far below anything a routing decision turns on,
    and the same approximation the visibility test already relies on.
    """
    distance = euclidean_distance(a, b)
    if distance <= 0.0:
        return 0.0
    if step is None:
        step = grid.resolution / 4.0
    samples = max(1, math.ceil(distance / step))
    total = 0.0
    for i in range(samples):
        # Midpoint of each sub-segment: sampling the endpoints instead
        # would count the two ends once each and weight a cell the
        # segment merely touches the same as one it crosses.
        t = (i + 0.5) / samples
        total += grid.traversal_at_world(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
    return (distance / samples) * total


def simplify_path(
    grid: OccupancyGrid, path: Sequence[Point2D], step: float | None = None
) -> tuple[Point2D, ...]:
    """Greedy shortcutting that keeps both endpoints and never costs more.

    From each anchor, jumps to the farthest waypoint that is both visible
    and **no more expensive** than the stretch of path it replaces.

    The cost test is what makes this safe on a graded grid, and without
    it the gradient would be pointless. A* spends real effort routing
    around an expensive band; a shortcutter that only asked "is anything
    blocking me" would pull the result straight back through it and hand
    back a path hugging the obstacle — the search's caution deleted in
    post-processing, silently, on every plan.

    On an ungraded grid every multiplier is ``1.0``, so a shortcut's cost
    is its length and a straight line between two points is never longer
    than the path through them: the test passes for free and this
    behaves exactly as it did before.
    """
    if len(path) <= 2:
        return tuple(path)
    result: list[Point2D] = [path[0]]
    anchor = 0
    last = len(path) - 1
    # Cost of the original path from each waypoint to the next, so the
    # comparison below is a prefix-sum lookup rather than a re-integration
    # of the same stretch once per candidate shortcut.
    leg = [segment_cost(grid, path[i], path[i + 1], step) for i in range(last)]
    cumulative = [0.0]
    for value in leg:
        cumulative.append(cumulative[-1] + value)
    while anchor < last:
        next_index = anchor + 1
        for j in range(last, anchor + 1, -1):
            if not has_line_of_sight(grid, path[anchor], path[j], step):
                continue
            original = cumulative[j] - cumulative[anchor]
            if segment_cost(grid, path[anchor], path[j], step) <= original + EPS:
                next_index = j
                break
        result.append(path[next_index])
        anchor = next_index
    return tuple(result)
