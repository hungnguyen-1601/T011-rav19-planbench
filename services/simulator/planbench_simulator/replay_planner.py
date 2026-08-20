"""The planner the explanation layer is handed, on this side of the seam — E6b.

:mod:`planbench_explanation.replay` states what a replay needs from a
planner and refuses to know what one is. This is the other half: it
turns a :class:`~planbench_explanation.replay.ReplayRequest` — cells,
geometry, two coordinates, a planner name and its knobs — into an actual
``OccupancyGrid`` and an actual planner, runs it, and reports the result
in the same terms the recording used.

**It lives here because both halves it needs already do.** The grid type
and the planner registry are the simulator's; importing them into the
explanation package would mean that package could only ever explain runs
produced by this repository at this version. Keeping the dependency
pointing this way is the same rule that stopped ``nav_stack`` importing
the explanation layer at module scope.

**The grid is rebuilt, not re-derived.** The snapshot holds the cells the
planner was handed *after* inflation and standing-room relaxation, so
this must not inflate them again: doing so would plan on a world the run
never saw and report the divergence as though the run were
irreproducible. The cells go in exactly as recorded.

**The harness reports its own identity.** ``planner_fingerprint`` is
computed from what this adapter actually configured, and
``execution_environment_ref`` is the build this process is running.
Echoing the record's values would make the comparison agree with itself,
and that comparison is the only thing standing between "the mechanism
was verified" and "some planner somewhere returned the same answer".
"""

from __future__ import annotations

from planbench_explanation.replay import ReplayPlan, ReplayRequest, ReplayUnavailable
from planbench_explanation.sidecar_writer import planner_fingerprint
from planbench_planning import AStarConfig, AStarPlanner, RRTStarConfig, RRTStarPlanner
from planbench_planning.common.base import GlobalPlanner
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.map import MapData
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.nav_stack import _plan_checksum

#: Planner name to (class, config class). Closed: a name this map does
#: not hold is a planner this harness cannot faithfully rebuild, and
#: guessing at the nearest match is how a replay ends up measuring a
#: different algorithm.
PLANNERS: dict[str, tuple[type[GlobalPlanner], type]] = {
    "astar": (AStarPlanner, AStarConfig),
    "rrtstar": (RRTStarPlanner, RRTStarConfig),
}

#: Planners whose result depends on a seed. Replaying one without the
#: seed grows a different tree, so the harness refuses instead.
SEEDED_PLANNERS: frozenset[str] = frozenset({"rrtstar"})


class SimulatorReplayPlanner:
    """Runs a recorded query again, with this repository's planners."""

    def __init__(self, *, execution_environment_ref: str) -> None:
        self.execution_environment_ref = execution_environment_ref

    def replay(self, request: ReplayRequest) -> ReplayPlan:
        planner = self._build(request)
        grid = OccupancyGrid(
            MapData(
                name="replay",
                width=request.width,
                height=request.height,
                resolution=request.resolution,
                origin=Pose2D(x=request.origin_x, y=request.origin_y, theta=0.0),
                cells=request.cells,
            )
        )
        result = planner.plan(
            grid,
            Point2D(x=request.start_x, y=request.start_y),
            Point2D(x=request.goal_x, y=request.goal_y),
        )
        fingerprint = planner_fingerprint(request.planner_name, dict(request.planner_parameters))
        if result.success:
            return ReplayPlan(
                outcome="path",
                output_plan_checksum=_plan_checksum(result),
                planner_fingerprint=fingerprint,
                execution_environment_ref=self.execution_environment_ref,
            )
        return ReplayPlan(
            outcome="no_path",
            failure_code=result.failure_reason or "no_global_path",
            planner_fingerprint=fingerprint,
            execution_environment_ref=self.execution_environment_ref,
        )

    def _build(self, request: ReplayRequest) -> GlobalPlanner:
        entry = PLANNERS.get(request.planner_name)
        if entry is None:
            raise ReplayUnavailable(
                "planner_not_in_harness",
                f"no planner named {request.planner_name!r} in this harness; known "
                f"planners are {sorted(PLANNERS)}. Substituting the nearest match "
                "would replay a different algorithm.",
            )
        planner_class, config_class = entry
        if request.planner_name in SEEDED_PLANNERS and request.seed is None:
            raise ReplayUnavailable(
                "seed_not_recorded",
                f"{request.planner_name} draws from a seed and the snapshot records "
                "none; replaying it would grow a different tree and the comparison "
                "would say the run was irreproducible when the harness simply guessed",
            )

        known = set(config_class.model_fields)
        config = config_class(
            **{key: value for key, value in request.planner_parameters.items() if key in known}
        )
        if request.planner_name in SEEDED_PLANNERS:
            return planner_class(config, episode_seed=request.seed)  # type: ignore[call-arg]
        return planner_class(config)  # type: ignore[call-arg]
