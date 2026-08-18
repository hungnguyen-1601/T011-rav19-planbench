"""What a plugin author can run before asking anyone to run their plugin.

**The checks here are the ones the host cannot make for you.** Preflight
answers *may this run* from declarations alone; this answers *does the
object behave the way its declarations promise*, which needs the plugin
in hand and a request to hand it.

Five of them are worth naming, because they catch things that otherwise
surface as a wrong number rather than an error:

**Determinism.** HĐ-4 requires a controller to give identical commands
for identical inputs, and *every* comparison this platform makes assumes
it. Nothing checks it at runtime: a plugin that consults the wall clock
or an unseeded generator produces a different episode each run, and the
paired statistics quietly measure noise. Two fresh instances given the
same first call must agree.

**"Optional" must actually be optional — including all at once.** A
plugin declaring two channels optional may still need *one of the two*;
withholding them one at a time would pass it, and the deployment that
offers neither would then fail mid-episode. So each optional is withheld
individually **and** all of them are withheld together.

**Undeclared reads.** The plugin is run with **exactly** the channels it
declared, and nothing else — anything it reaches for beyond that names
itself in the failure. This is a manifest bug, and finding it here is
the difference between fixing a line of JSON and debugging an episode.

**Payload immutability.** The request models are frozen, so reassigning
a field already fails; what nothing stops is writing *into* a mutable
payload. The host hands one envelope to every consumer granted it, so a
dict scribbled on by one plugin is a different world for the next.

**Global plugins are checked too**, through :func:`check_global_plugin`.
They present ``plan()`` and no ``step()``, so running them through the
local suite would crash on the first call — a suite that only fits two
of the three roles is a suite that tells the third nothing.

**Findings are returned, never raised**, and that is enforced rather
than intended: constructing the plugin, resetting it, reading its
action and copying its request all happen inside a guard, because an
author whose constructor raises wants a finding that says so, not a
traceback out of the checker.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from planbench_plugin_sdk.manifest import PluginManifest
from planbench_plugin_sdk.requests import (
    GlobalPlanRequest,
    LocalResetRequest,
    LocalStepRequest,
)

Severity = Literal["error", "warning"]

#: What each role must present to be driven by the host.
ROLE_METHODS: dict[str, tuple[str, ...]] = {
    "global": ("plan",),
    "local": ("reset", "step"),
    "monolithic": ("reset", "step"),
}


@dataclass(frozen=True)
class Finding:
    """One thing a plugin does that its declarations do not support."""

    check: str
    severity: Severity
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check}: {self.message}"


@dataclass(frozen=True)
class ConformanceReport:
    findings: tuple[Finding, ...] = ()

    @property
    def passed(self) -> bool:
        """Warnings do not fail a plugin. They are things an author
        should know and may have decided on purpose; errors are things
        the host will act on wrongly."""
        return not any(finding.severity == "error" for finding in self.findings)

    def render(self) -> str:
        if not self.findings:
            return "conformance: no findings"
        return "\n".join(str(finding) for finding in self.findings)


def check_local_plugin(
    manifest: PluginManifest,
    factory: Callable[[], Any],
    step_request: LocalStepRequest,
    reset_request: LocalResetRequest | None = None,
) -> ConformanceReport:
    """Every behavioural check for a local or monolithic plugin.

    ``factory`` rather than an instance: determinism is checked from a
    *fresh* plugin, because a stateful controller is allowed to answer
    differently on its second tick and comparing tick one with tick two
    would fail every tracker for doing its job.

    **Each check gets its own deep copies of both requests.** Sharing one
    was enough, twice, to make this suite's verdict depend on the order
    its own checks happened to run in: a mutating plugin scribbled on the
    shared request during an earlier check, and the immutability check
    then compared a dirty request against itself and passed.
    """
    reference_reset = reset_request or LocalResetRequest()

    def fresh_step() -> LocalStepRequest:
        return step_request.model_copy(deep=True)

    def fresh_reset() -> LocalResetRequest:
        return reference_reset.model_copy(deep=True)

    findings: list[Finding] = []
    built = _guard("construction", factory)
    if built.finding:
        return ConformanceReport((built.finding,))
    findings += _check_shape(manifest, built.value)
    findings += _check_determinism(factory, fresh_reset, fresh_step)
    findings += _check_optionals_are_optional(manifest, factory, fresh_reset, fresh_step)
    findings += _check_only_declared_channels(manifest, factory, fresh_reset, fresh_step)
    findings += _check_request_not_mutated(factory, fresh_reset, fresh_step)
    return ConformanceReport(tuple(findings))


def check_global_plugin(
    manifest: PluginManifest,
    factory: Callable[[], Any],
    plan_request: GlobalPlanRequest,
) -> ConformanceReport:
    """The same discipline for the role that has no ``step()``.

    A global planner is checked for the two things a path can be wrong
    about before anybody drives it: that two identical queries produce
    the identical path, and that every waypoint is a finite number. A
    path with a NaN in it fails much later, inside a follower, as a robot
    that stops for no stated reason.
    """
    findings: list[Finding] = []
    built = _guard("construction", factory)
    if built.finding:
        return ConformanceReport((built.finding,))
    findings += _check_shape(manifest, built.value)

    def fresh() -> GlobalPlanRequest:
        return plan_request.model_copy(deep=True)

    paths: list[tuple] = []
    for _ in range(2):
        attempt = _guard("plan", lambda: factory().plan(fresh()))
        if attempt.finding:
            return ConformanceReport((*findings, attempt.finding))
        result = attempt.value
        path = tuple(_points_of(result))
        if not all(math.isfinite(value) for point in path for value in point):
            findings.append(
                Finding(
                    "path",
                    "error",
                    "plan() returned a path containing a non-finite coordinate; that "
                    "fails much later, inside a follower, as a robot that stops for no "
                    "stated reason",
                )
            )
            return ConformanceReport(tuple(findings))
        paths.append(path)

    if paths[0] != paths[1]:
        findings.append(
            Finding(
                "determinism",
                "error",
                "two fresh plugins given the same query returned different paths. A "
                "sampling planner satisfies HĐ-4 by drawing from a generator seeded "
                "from its own configuration — never from process-global randomness",
            )
        )

    probe = fresh()
    reference = probe.model_dump(mode="json")
    mutated = _guard("plan", lambda: factory().plan(probe))
    if not mutated.finding and probe.model_dump(mode="json") != reference:
        findings.append(_mutation_finding())
    return ConformanceReport(tuple(findings))


# -- guarded execution -------------------------------------------------


@dataclass(frozen=True)
class _Guarded:
    value: Any = None
    finding: Finding | None = None


def _guard(check: str, call: Callable[[], Any]) -> _Guarded:
    """Run author code and turn any failure into a finding.

    The module promises findings rather than exceptions, and a promise
    kept only for the failures somebody remembered to wrap is not kept.
    """
    try:
        return _Guarded(value=call())
    except Exception as error:  # noqa: BLE001 - foreign code, any failure is a finding
        return _Guarded(finding=Finding(check, "error", f"raised {error!r}"))


# -- individual checks -------------------------------------------------


def _check_shape(manifest: PluginManifest, plugin: Any) -> list[Finding]:
    findings: list[Finding] = []
    for method in ROLE_METHODS.get(manifest.role, ()):
        if not callable(getattr(plugin, method, None)):
            findings.append(
                Finding(
                    "role",
                    "error",
                    f"role {manifest.role!r} is driven through {method}(), which this "
                    "object does not have",
                )
            )
    if not getattr(plugin, "name", ""):
        findings.append(
            Finding("name", "error", "every trace and report identifies a candidate by name")
        )
    return findings


def _action_of(result: Any) -> tuple[float, float] | None:
    action = getattr(result, "action", result)
    linear = getattr(action, "linear_velocity", None)
    angular = getattr(action, "angular_velocity", None)
    if linear is None and isinstance(action, dict):
        linear, angular = action.get("linear_velocity"), action.get("angular_velocity")
    try:
        return float(linear), float(angular)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _points_of(result: Any) -> list[tuple[float, float]]:
    path = getattr(result, "path", ()) or ()
    points = []
    for point in path:
        x = getattr(point, "x", None)
        y = getattr(point, "y", None)
        if x is None and isinstance(point, (list, tuple)) and len(point) >= 2:
            x, y = point[0], point[1]
        points.append((float(x), float(y)))  # type: ignore[arg-type]
    return points


def _one_step(
    factory: Callable[[], Any],
    fresh_reset: Callable[[], LocalResetRequest],
    request: LocalStepRequest,
    check: str,
) -> _Guarded:
    def run() -> Any:
        plugin = factory()
        plugin.reset(fresh_reset())
        return plugin.step(request)

    return _guard(check, run)


def _check_determinism(
    factory: Callable[[], Any],
    fresh_reset: Callable[[], LocalResetRequest],
    fresh_step: Callable[[], LocalStepRequest],
) -> list[Finding]:
    commands = []
    for _ in range(2):
        attempt = _one_step(factory, fresh_reset, fresh_step(), "determinism")
        if attempt.finding:
            return [attempt.finding]
        action = _action_of(attempt.value)
        if action is None:
            return [
                Finding(
                    "action",
                    "error",
                    f"step() returned {type(attempt.value).__name__}, which carries no "
                    "numeric linear_velocity/angular_velocity",
                )
            ]
        if not all(math.isfinite(value) for value in action):
            return [Finding("action", "error", f"step() returned a non-finite command {action}")]
        commands.append(action)

    if commands[0] != commands[1]:
        return [
            Finding(
                "determinism",
                "error",
                f"two fresh plugins given the same first step answered {commands[0]} and "
                f"{commands[1]}. HĐ-4 requires identical commands for identical inputs, and "
                "every paired comparison on this platform assumes it — a clock or an "
                "unseeded generator here turns a result into noise",
            )
        ]
    return []


def _without(request: LocalStepRequest, capabilities: Sequence[str]) -> LocalStepRequest:
    return request.model_copy(
        update={
            "channels": tuple(
                envelope
                for envelope in request.channels
                if envelope.capability not in set(capabilities)
            )
        }
    )


def _check_optionals_are_optional(
    manifest: PluginManifest,
    factory: Callable[[], Any],
    fresh_reset: Callable[[], LocalResetRequest],
    fresh_step: Callable[[], LocalStepRequest],
) -> list[Finding]:
    optional = manifest.requirements.optional
    if not optional:
        return []

    findings: list[Finding] = []
    # Each on its own, **and then all of them together**. Dropping one at
    # a time passes a plugin that needs any one of two, and the
    # deployment offering neither is exactly the one the label promised
    # would work.
    combinations: list[tuple[str, ...]] = [(capability,) for capability in optional]
    if len(optional) > 1:
        combinations.append(tuple(optional))

    for withheld in combinations:
        attempt = _one_step(
            factory, fresh_reset, _without(fresh_step(), withheld), "optional"
        )
        if attempt.finding:
            named = list(withheld)
            findings.append(
                Finding(
                    "optional",
                    "error",
                    f"{named} are declared optional but step() failed without them "
                    f"({attempt.finding.message}). The host believes the label and will "
                    "run this plugin on a deployment that does not offer them",
                )
            )
    return findings


def _check_only_declared_channels(
    manifest: PluginManifest,
    factory: Callable[[], Any],
    fresh_reset: Callable[[], LocalResetRequest],
    fresh_step: Callable[[], LocalStepRequest],
) -> list[Finding]:
    """Run with exactly what the manifest declared, and nothing more.

    A plugin that works in the author's harness because the harness was
    generous, and fails in a deployment that grants precisely what was
    asked for, has a manifest bug. Finding it here costs a line of JSON;
    finding it later costs an episode.
    """
    declared = {
        *manifest.requirements.all_of,
        *manifest.requirements.any_of,
        *manifest.requirements.optional,
    }
    request = fresh_step()
    extra = [
        envelope.capability
        for envelope in request.channels
        if envelope.capability not in declared
    ]
    if not extra:
        return []

    attempt = _one_step(factory, fresh_reset, _without(request, extra), "undeclared")
    if attempt.finding:
        return [
            Finding(
                "undeclared",
                "error",
                f"step() failed when given only its declared channels — the sample "
                f"request also carried {extra}, and something in the plugin depends on "
                f"them. Declare them, or stop reading them ({attempt.finding.message})",
            )
        ]
    return []


def _mutation_finding() -> Finding:
    return Finding(
        "immutability",
        "error",
        "the plugin wrote into its request. The models are frozen, so this was a "
        "mutable payload — and the host hands that same envelope to every consumer "
        "granted it, so the next plugin now reads a different world and the "
        "difference belongs to no candidate",
    )


def _check_request_not_mutated(
    factory: Callable[[], Any],
    fresh_reset: Callable[[], LocalResetRequest],
    fresh_step: Callable[[], LocalStepRequest],
) -> list[Finding]:
    probe = fresh_step()
    reference = probe.model_dump(mode="json")
    reset_probe = fresh_reset()
    reset_reference = reset_probe.model_dump(mode="json")

    def run() -> Any:
        plugin = factory()
        plugin.reset(reset_probe)
        return plugin.step(probe)

    attempt = _guard("immutability", run)
    if attempt.finding:
        return []  # already reported by the determinism check
    if probe.model_dump(mode="json") != reference:
        return [_mutation_finding()]
    if reset_probe.model_dump(mode="json") != reset_reference:
        return [
            Finding(
                "immutability",
                "error",
                "reset() wrote into its request. The deployment's declarations are "
                "shared, so a plugin that edits them changes what the deployment says "
                "for everything measured after it",
            )
        ]
    return []


def check_declarations(manifest: PluginManifest, granted: Sequence[str]) -> ConformanceReport:
    """Static checks an author can run with no plugin object at all."""
    findings: list[Finding] = []
    missing = manifest.requirements.missing_from(frozenset(granted))
    if missing:
        findings.append(
            Finding("requirements", "warning", f"not satisfied by this deployment: {list(missing)}")
        )
    if manifest.role == "global" and manifest.requires_global_path:
        findings.append(
            Finding(
                "role",
                "error",
                "a global plugin produces the path; requiring one describes a local plugin",
            )
        )
    overlap = set(manifest.requirements.all_of) & set(manifest.requirements.optional)
    if overlap:
        findings.append(
            Finding(
                "requirements",
                "error",
                f"{sorted(overlap)} are declared both required and optional; the host "
                "cannot honour both readings and would pick one silently",
            )
        )
    return ConformanceReport(tuple(findings))
