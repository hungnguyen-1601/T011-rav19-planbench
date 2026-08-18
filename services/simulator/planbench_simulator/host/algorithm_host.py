"""The host: guardrails between the loop and whatever runs inside.

Three semantics, stated once and tested (H2 DoD):

**Crash.** A plugin exception during a *step* becomes a safe stop — a
zero command with the crash in ``failure_reason``, which the loop
records as a local-planner failure event, exactly where a controller's
own refusals already go. A crash during a *global plan* becomes a
failed ``PlanResult``, which the loop treats as "no route", replannable
like any other. A crash during *reset* raises: an episode whose
controller cannot even initialise is misconfigured, and driving a robot
with an uninitialised controller to "keep going" would manufacture data.

**Invalid output.** A step that returns anything but a
``LocalPlanResult`` is a contract violation, handled like a crash: safe
stop, counted. The models themselves already refuse NaN and infinite
commands (``allow_inf_nan=False``), so "invalid" here means the shape,
not the values.

**Deadline.** The in-process lane *observes* the control deadline and
counts misses in :class:`HostStats`; it cannot preempt a Python call
mid-flight, and pretending otherwise would be a timeout that only fires
when it was not needed. Preemptive enforcement is what the subprocess
lane exists for (H7). Nothing about a miss enters the trace — latency
columns already carry the wall-clock truth, and gate G4 reads those.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from planbench_plugin_sdk import GlobalPlanRequest, LocalResetRequest, LocalStepRequest

from planbench_planning.common.base import PlanResult
from planbench_planning.common.local_base import LocalPlanResult
from planbench_schemas.robot import SimAction
from planbench_simulator.host.lifecycle import HostedGlobalPlugin, HostedLocalPlugin


class HostPluginError(RuntimeError):
    """A plugin failed somewhere the host must not paper over."""


@dataclass
class HostStats:
    """What the host observed, for diagnostics — never for the trace."""

    plan_calls: int = 0
    step_calls: int = 0
    crashes: int = 0
    invalid_outputs: int = 0
    deadline_misses: int = 0
    notes: list[str] = field(default_factory=list)


def _safe_stop(reason: str) -> LocalPlanResult:
    return LocalPlanResult(
        action=SimAction(linear_velocity=0.0, angular_velocity=0.0),
        failure_reason=reason,
    )


class AlgorithmHost:
    """One episode's algorithms, behind one mediation point.

    Owns at most one global plugin and one local (or monolithic) plugin
    — the shape of an episode, not of a registry. Construction is cheap
    and per-episode, like the planners it hosts.
    """

    def __init__(
        self,
        *,
        global_plugin: HostedGlobalPlugin | None = None,
        local_plugin: HostedLocalPlugin | None = None,
        control_deadline_s: float | None = None,
    ) -> None:
        self._global = global_plugin
        self._local = local_plugin
        self._deadline_s = control_deadline_s
        self.stats = HostStats()

    # -- global --------------------------------------------------------

    @property
    def global_name(self) -> str:
        assert self._global is not None
        return self._global.name

    def plan_global(self, request: GlobalPlanRequest) -> PlanResult:
        if self._global is None:
            raise HostPluginError("this host was built without a global plugin")
        self.stats.plan_calls += 1
        try:
            result = self._global.plan(request)
        except Exception as error:  # noqa: BLE001 - the boundary this host exists for
            self.stats.crashes += 1
            return PlanResult(
                success=False,
                failure_reason=f"global plugin {self._global.name!r} crashed: {error!r}",
            )
        if not isinstance(result, PlanResult):
            self.stats.invalid_outputs += 1
            return PlanResult(
                success=False,
                failure_reason=(
                    f"global plugin {self._global.name!r} returned "
                    f"{type(result).__name__}, not a PlanResult"
                ),
            )
        return result

    # -- local ---------------------------------------------------------

    @property
    def local_name(self) -> str:
        assert self._local is not None
        return self._local.name

    @property
    def local_control_period(self) -> float | None:
        assert self._local is not None
        return self._local.control_period

    @property
    def local_diagnostics(self):
        """The plugin's counters, if it keeps any — same probe the loop
        has always used (``_controller_counters``), forwarded so the wrap
        does not silently discard an episode's diagnostics."""
        assert self._local is not None
        return getattr(self._local, "diagnostics", None)

    def reset_local(self, request: LocalResetRequest) -> None:
        if self._local is None:
            raise HostPluginError("this host was built without a local plugin")
        try:
            self._local.reset(request)
        except Exception as error:
            raise HostPluginError(
                f"local plugin {self._local.name!r} crashed during reset: {error!r}; "
                "an episode whose controller cannot initialise is misconfigured, and "
                "running it anyway would manufacture data"
            ) from error

    def step_local(self, request: LocalStepRequest) -> LocalPlanResult:
        if self._local is None:
            raise HostPluginError("this host was built without a local plugin")
        self.stats.step_calls += 1
        started = time.perf_counter()
        try:
            result = self._local.step(request)
        except Exception as error:  # noqa: BLE001 - the boundary this host exists for
            self.stats.crashes += 1
            return _safe_stop(f"local plugin {self._local.name!r} crashed: {error!r}; safe stop")
        if not isinstance(result, LocalPlanResult):
            self.stats.invalid_outputs += 1
            return _safe_stop(
                f"local plugin {self._local.name!r} returned "
                f"{type(result).__name__}, not a LocalPlanResult; safe stop"
            )
        if self._deadline_s is not None and time.perf_counter() - started > self._deadline_s:
            # Observed, never enforced in this lane — see module docstring.
            self.stats.deadline_misses += 1
        return result
