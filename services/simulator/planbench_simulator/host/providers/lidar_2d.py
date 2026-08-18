"""``lidar_2d`` — planar ranges, derived from the one measurement taken.

**Derived, not re-measured.** This provider depends on the observation
channel instead of calling the engine itself. Two independent reads of
the sensor in one tick would draw noise twice, and two consumers would
then be navigating two slightly different worlds while a report claimed
they saw the same one.

The capability keeps its **v1 token spelling**, not the URI: that is the
canonical form the alias bridge reduces to (H1a), and every stored
``candidate_id`` that ever declared LiDAR declared it this way.
"""

from __future__ import annotations

from typing import Any

from planbench_simulator.host.providers.base import Provider
from planbench_simulator.host.providers.legacy_observation import LEGACY_OBSERVATION
from planbench_simulator.host.runtime_view import ProviderRuntimeView

LIDAR_2D = "lidar_2d"


class Lidar2DProvider(Provider):
    """Range returns for this tick."""

    capability = LIDAR_2D
    cadence = "per_tick"
    provenance = "deployment"
    depends_on = (LEGACY_OBSERVATION,)
    stream_id = 3

    def __init__(self) -> None:
        self._ranges: tuple[float, ...] = ()

    def reset(self) -> None:
        self._ranges = ()

    def advance(
        self, tick: int, now: float, view: ProviderRuntimeView, inputs: dict[str, Any]
    ) -> None:
        del tick, now, view
        observation = inputs[LEGACY_OBSERVATION]
        self._ranges = () if observation is None else tuple(observation.lidar_ranges)

    def read(self) -> tuple[float, ...]:
        return self._ranges
