"""``legacy-observation@1`` — the whole ``Observation``, unchanged.

The bridge channel: every controller written before the host reads this
object, and H2's facade already delivers it. Keeping it as its own
capability rather than decomposing it is what lets a legacy controller
and a channel-native plugin run side by side in one episode without
either being translated — and translation is the only way this layer
could break parity.

It is also the source the finer channels derive from, which is why they
declare it as a dependency instead of calling the engine twice: two
calls to ``get_observation`` in one tick would draw sensor noise twice
and hand two controllers two different worlds.
"""

from __future__ import annotations

from typing import Any

from planbench_schemas.episode import Observation
from planbench_simulator.host.providers.base import Provider
from planbench_simulator.host.runtime_view import ProviderRuntimeView

LEGACY_OBSERVATION = "planbench://channel/legacy-observation@1"


class LegacyObservationProvider(Provider):
    """One ``Observation`` per control tick, exactly as measured."""

    capability = LEGACY_OBSERVATION
    cadence = "per_tick"
    provenance = "deployment"
    stream_id = 2

    def __init__(self) -> None:
        self._observation: Observation | None = None

    def reset(self) -> None:
        self._observation = None

    def advance(
        self, tick: int, now: float, view: ProviderRuntimeView, inputs: dict[str, Any]
    ) -> None:
        del tick, now, inputs
        self._observation = view.measured_observation()

    def read(self) -> Observation | None:
        return self._observation
