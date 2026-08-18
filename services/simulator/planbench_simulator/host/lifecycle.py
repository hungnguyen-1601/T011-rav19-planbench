"""What a hosted plugin is, and how in-process channels carry data.

**The in-process lane carries native objects.** ``python-object/v1`` is
a real codec whose encode and decode are both the identity function —
the envelope's payload *is* the ``OccupancyGrid`` or ``Observation``.
That is what makes byte-level parity with the pre-host runtime possible
at all; real serialisation arrives with the subprocess lane (H7), where
parity is measured against *this* lane rather than assumed.

The protocols return the platform's native result models
(``PlanResult``, ``LocalPlanResult``) for the same reason: in the
trusted lane the host's job is mediation and guardrails, not
translation, and a lossy translation here would show up as a parity
diff the wrap cannot explain. External runtimes speak the SDK response
models and their adapter does the mapping — with the trust semantics of
plan §5.9 rule 6 attached.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from planbench_plugin_sdk import (
    ChannelEnvelope,
    GlobalPlanRequest,
    LocalResetRequest,
    LocalStepRequest,
)

from planbench_planning.common.base import PlanResult
from planbench_planning.common.local_base import LocalPlanResult

#: The planning grid, as the legacy stack hands it over. ``on_change``:
#: it is rebuilt per planning call (initial plan, replans), not per tick.
GRID_CHANNEL = "planbench://channel/planning-grid@1"

#: The engine's ``Observation`` — the exact object ``get_observation``
#: returns, one per control tick.
OBSERVATION_CHANNEL = "planbench://channel/legacy-observation@1"


def channel_payload(channels: tuple[ChannelEnvelope, ...], capability: str) -> Any:
    """The payload of one granted channel, or a loud absence.

    Plugins receive exactly what they were granted, so a missing channel
    here is a host wiring defect — the error says which capability, not
    ``KeyError: 0``.
    """
    for envelope in channels:
        if envelope.capability == capability:
            return envelope.payload
    raise LookupError(
        f"no channel {capability!r} in this request; granted: "
        f"{[envelope.capability for envelope in channels]}"
    )


@runtime_checkable
class HostedGlobalPlugin(Protocol):
    """One global planning capability behind the host."""

    @property
    def name(self) -> str: ...

    def plan(self, request: GlobalPlanRequest) -> PlanResult: ...


@runtime_checkable
class HostedLocalPlugin(Protocol):
    """One local controller (or monolithic policy) behind the host."""

    @property
    def name(self) -> str: ...

    @property
    def control_period(self) -> float | None: ...

    def reset(self, request: LocalResetRequest) -> None: ...

    def step(self, request: LocalStepRequest) -> LocalPlanResult: ...
