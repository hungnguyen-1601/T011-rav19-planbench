"""``static-costmap@1`` — the planning grid, static for the episode.

The first non-``per_tick`` built-in, and the reason the cadence rules
had to be written per cadence rather than as one equality. This grid is
built once from the deployment's map and does not change; a rule
demanding ``produced_at == now`` would force it to re-stamp itself every
tick, teaching the honest implementation to lie about freshness. It
carries a fixed revision instead, and the host stamps its time once.
"""

from __future__ import annotations

from typing import Any

from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.host.providers.base import Provider
from planbench_simulator.host.runtime_view import ProviderRuntimeView

STATIC_COSTMAP = "planbench://channel/static-costmap@1"


class StaticCostmapProvider(Provider):
    """The episode's planning grid, produced once."""

    capability = STATIC_COSTMAP
    cadence = "static"
    provenance = "deployment"
    stream_id = 4

    def __init__(self) -> None:
        self._grid: OccupancyGrid | None = None

    def reset(self) -> None:
        self._grid = None

    def advance(
        self, tick: int, now: float, view: ProviderRuntimeView, inputs: dict[str, Any]
    ) -> None:
        del tick, now, inputs
        if self._grid is None:
            self._grid = view.planning_grid()

    def read(self) -> OccupancyGrid | None:
        return self._grid

    def revision(self) -> int:
        """One, for the whole episode. A static channel that bumped its
        revision would not be static, and the monitor says so."""
        return 1
