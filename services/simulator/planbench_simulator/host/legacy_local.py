"""The legacy local controllers, wearing the plugin contract.

**This is where kwargs probing goes to be quarantined** (plan §7.2).
The loop's ``_reset_local`` probes a controller's ``reset`` signature by
name — the mechanism that silently lost ``sensor_noise`` once. New
plugins never see it: their reset request carries every deployment
declaration in ``declared``, present whether or not they read it. The
legacy controllers, which cannot be edited without changing candidate
identity, keep receiving exactly the kwargs their signatures accept —
and the probe now lives here, in one adapter, instead of on the
extension surface.

The probe forwards the declared *value* whenever the name is accepted,
including ``None`` — identical to ``_reset_local``, because "the
deployment declared nothing" and "the parameter never arrived" are the
same distinction that bug was about.
"""

from __future__ import annotations

import inspect

from planbench_plugin_sdk import LocalResetRequest, LocalStepRequest

from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.geometry import Point2D
from planbench_simulator.host.lifecycle import OBSERVATION_CHANNEL, channel_payload

#: The declarations a legacy controller may accept by name, in the order
#: ``_reset_local`` has always considered them.
_PROBED_DECLARATIONS = ("envelope", "obstacle_speed", "sensor_noise")


class LegacyLocalPlugin:
    """One registry local controller behind the host boundary."""

    def __init__(self, inner: LocalPlanner) -> None:
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def control_period(self) -> float | None:
        return self._inner.control_period

    @property
    def diagnostics(self):
        """Forwarded, not copied: the loop folds counters across resets,
        and handing it a snapshot would freeze them."""
        return getattr(self._inner, "diagnostics", None)

    def reset(self, request: LocalResetRequest) -> None:
        path = tuple(Point2D(x=x, y=y) for x, y in request.global_path)
        robot = request.robot["robot_config"]
        accepted = inspect.signature(self._inner.reset).parameters
        extra = {
            name: request.declared.get(name) for name in _PROBED_DECLARATIONS if name in accepted
        }
        self._inner.reset(path, robot, **extra)  # type: ignore[arg-type]

    def step(self, request: LocalStepRequest) -> LocalPlanResult:
        return self._inner.compute(
            request.state["robot_state"],
            channel_payload(request.channels, OBSERVATION_CHANNEL),
        )
