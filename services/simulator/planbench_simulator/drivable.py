r"""L4 — is a global path one the local controller could actually drive?

**L1 says global may only return paths inside the hard feasible set local
can execute.** A rule nobody checks is a comment, so this is the check.
It answers one question and refuses the neighbouring ones: *does this
path stay outside the hard set's boundary*, not *is it a good path*, not
*will the controller succeed*.

**Continuous, never on the grid.** The hard set is defined in
:mod:`planbench_schemas.feasibility` as a distance in metres, and the
grid is a conservative *approximation* of it whose extra caution is a
property of the map's resolution. Asking the grid would confuse
"infeasible" with "coarsely rasterised" — which is precisely the
confusion that stranded a robot for 55 replans, so the validator that
guards against it must not repeat it. A path is therefore sampled along
its segments and measured against obstacle geometry.

**Sampled at a step small against the clearance, and the corners are
always sampled.** A waypoint is where a path is most likely to cut a
corner, and a sampler that only landed on interior points could step
straight over the one that matters.

The one thing this deliberately does *not* check is the comfort margin.
A path running closer than a candidate would like is legal and is
supposed to cost that candidate something in :meth:`DWAPlanner._score` —
if this rejected it, L2 would collapse back into "both layers must use
the same keep-out", which is the design this replaced.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from planbench_schemas.feasibility import SafetyEnvelope, hard_clearance
from planbench_schemas.geometry import Point2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle
from planbench_simulator.collision import clearance_to_obstacles
from planbench_simulator.grid import OccupancyGrid

__all__ = ["DrivabilityReport", "path_is_drivable"]

#: Fraction of the hard clearance a sample step may cover. At a fifth,
#: the deepest an unsampled midpoint can dip below a sampled pair is a
#: small fraction of the margin being tested, and a violation has to be a
#: real one rather than an artifact of the sampler's stride.
_STEP_FRACTION = 0.2


@dataclass(frozen=True)
class DrivabilityReport:
    """Where a path leaves the hard feasible set, and by how much.

    Both clearances are **surface to surface**: the room left between the
    robot's body and the obstacle's, which is the quantity a person reads
    off a screen. The footprint is therefore already spent, and what has
    to remain is the deployment's safety envelope — zero for a deployment
    declaring no localisation error, which is right: with an exact pose
    estimate the geometric body *is* the whole hard boundary.

    ``worst_clearance`` is reported whether or not the path passes,
    because "it passed" and "it passed with 2 mm to spare" are different
    answers and a boolean cannot tell them apart.
    """

    drivable: bool
    required_clearance: float
    worst_clearance: float
    worst_point: Point2D | None

    @property
    def shortfall(self) -> float:
        """How far inside the boundary the worst sample reached."""
        return max(0.0, self.required_clearance - self.worst_clearance)

    def describe(self) -> str:
        if self.drivable:
            return (
                f"drivable: closest approach {self.worst_clearance:.3f} m "
                f"against a required {self.required_clearance:.3f} m"
            )
        where = (
            f" at ({self.worst_point.x:.2f}, {self.worst_point.y:.2f})"
            if self.worst_point is not None
            else ""
        )
        return (
            f"not drivable{where}: clearance {self.worst_clearance:.3f} m is "
            f"{self.shortfall:.3f} m inside the hard boundary of "
            f"{self.required_clearance:.3f} m"
        )


def _samples(path: Sequence[Point2D], step: float) -> Iterable[Point2D]:
    """Every waypoint, plus interior points no further apart than ``step``."""
    if not path:
        return
    yield path[0]
    for start, end in zip(path, path[1:], strict=False):
        span = math.hypot(end.x - start.x, end.y - start.y)
        for index in range(1, max(1, int(math.ceil(span / step)))):
            fraction = index * step / span
            yield Point2D(
                x=start.x + (end.x - start.x) * fraction, y=start.y + (end.y - start.y) * fraction
            )
        yield end


def path_is_drivable(
    path: Sequence[Point2D],
    robot: RobotConfig,
    envelope: SafetyEnvelope,
    obstacles: Iterable[CircleObstacle | RectangleObstacle] = (),
    grid: OccupancyGrid | None = None,
) -> DrivabilityReport:
    """Does every point of ``path`` stay outside the hard feasible set?

    The signature is the contract in miniature: a robot, the
    **deployment's** envelope, and the world. No candidate configuration
    reaches it, so a controller cannot make a path "undrivable" by
    preferring more room, and a planner cannot make one drivable by
    inflating less.

    ``grid`` covers static geometry the map holds as cells; ``obstacles``
    covers shapes, including the dynamic ones at the instant the path was
    planned. Pass both when both exist — a path clear of every cart and
    straight through a wall is not drivable.

    An empty path is drivable in the same sense an empty sum is zero:
    there is nothing in it that violates anything. Callers wanting "the
    planner returned nothing" should ask :attr:`PlanResult.success`,
    which is the question they mean.
    """
    required = envelope.position_uncertainty_m
    worst = math.inf
    worst_point: Point2D | None = None
    step = max(hard_clearance(robot, envelope) * _STEP_FRACTION, 1e-3)
    for point in _samples(path, step):
        # Surface-to-surface: the footprint is inside `clearance_to_obstacles`
        # already, so what comes back is the room left over — and the room
        # that must be left over is exactly the envelope.
        clearance = clearance_to_obstacles(point, robot.radius, obstacles, grid)
        if clearance < worst:
            worst = clearance
            worst_point = point
    if worst is math.inf:
        return DrivabilityReport(True, required, math.inf, None)
    return DrivabilityReport(worst >= required, required, worst, worst_point)
