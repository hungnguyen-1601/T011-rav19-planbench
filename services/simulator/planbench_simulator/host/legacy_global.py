"""The legacy global planners, wearing the plugin contract.

Wraps an unchanged ``GlobalPlanner``. The request's start and goal are
plain floats and are rebuilt into ``Point2D`` — float-identical, since
no arithmetic touches them — and the grid arrives as the native object
on the in-process channel. Everything the planner returns passes through
untouched: parity is not a property this adapter maintains, it is one
it cannot break, because it computes nothing.
"""

from __future__ import annotations

from planbench_plugin_sdk import GlobalPlanRequest

from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_schemas.geometry import Point2D
from planbench_simulator.host.lifecycle import GRID_CHANNEL, channel_payload


class LegacyGlobalPlugin:
    """One registry global planner behind the host boundary."""

    def __init__(self, inner: GlobalPlanner) -> None:
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    def plan(self, request: GlobalPlanRequest) -> PlanResult:
        grid = channel_payload(request.channels, GRID_CHANNEL)
        return self._inner.plan(
            grid,
            Point2D(x=request.start[0], y=request.start[1]),
            Point2D(x=request.goal[0], y=request.goal[1]),
        )
