"""Preflight: may this plugin run here, and under what conditions (H4).

The gate before an episode, and the plan is explicit about why it exists
before rather than during: a candidate that cannot run must say so while
nobody has spent a sweep on it, and it must say *what is missing* rather
than "incompatible".

**Every problem, one pass.** The resolver never returns at the first
refusal. An operator who fixes the missing provider only to discover the
runtime lane is also absent has been made to run preflight twice for one
misconfiguration, and the second discovery was available the whole time.

**Registration and runnability are different answers** (§5.1). A plugin
with a valid manifest is registered whatever this resolver decides; what
it decides is which *kind* of not-yet-runnable it is, because "the
deployment owns no tracker" and "this host cannot drive an Ackermann
robot" send whoever reads it to two different places.

The report is also where the host's conditions become concrete: the
resolved provider graph, the adapter chain and the runtime profile are
folded into :class:`~planbench_benchmark.fingerprint.HostConditions`,
which flows into the one execution fingerprint the platform has — never
into a second hash of its own (§7.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from planbench_plugin_sdk import PluginManifest, Provenance

from planbench_benchmark.fingerprint import HostConditions
from planbench_simulator.host.fairness_policy import EvidenceClass, FairnessPolicy
from planbench_simulator.host.provider_graph import ProviderGraph

#: §5.1's registration states. ``quarantined`` is reached at discovery
#: (a manifest that contradicts another's schema digest), never here —
#: this resolver only ever sees manifests that already parsed.
RegistrationState = Literal[
    "registered_and_runnable",
    "registered_but_missing_provider",
    "registered_but_missing_runtime",
    "registered_but_incompatible",
]


@dataclass(frozen=True)
class HostSupport:
    """What this host can actually execute (§5.6).

    Deliberately a small closed set, and deliberately *not* extended to
    dodge a refusal: the plan says a plugin asking for something unbuilt
    stays registered and incompatible, and opening the physics to avoid
    a correct refusal would be answering the wrong complaint.
    """

    action_types: frozenset[str] = frozenset({"continuous-velocity@1", "global-path@1"})
    robot_dynamics: frozenset[str] = frozenset({"differential-drive@1"})
    execution_models: frozenset[str] = frozenset({"synchronous-step@1"})
    #: ``subprocess`` joined on 2026-08-18, when H7 built the lane —
    #: not when the plan named it. A host that declared support for a
    #: lane it had not implemented would let preflight pass a plugin
    #: straight into a loader that could not start it, turning a clean
    #: refusal into a crash one phase later.
    runtime_lanes: frozenset[str] = frozenset({"python_in_process", "subprocess"})


@dataclass(frozen=True)
class ProviderOwnership:
    """Who owns each resolved provider, and therefore what it changes.

    The three-way split of §7.1, kept as data because accounting, the
    fingerprint and candidate identity each read a different third of it:

    * ``candidate`` — part of the candidate; changes ``candidate_id``.
    * ``deployment`` — an execution condition; changes the fingerprint.
    * ``oracle`` — a condition too, and it also demotes the evidence
      class, which is why it is not folded into ``deployment``.
    """

    candidate_owned: tuple[tuple[str, str], ...] = ()
    deployment_owned: tuple[tuple[str, str], ...] = ()
    oracle_owned: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_graph(cls, graph: ProviderGraph) -> ProviderOwnership:
        buckets: dict[Provenance, list[tuple[str, str]]] = {
            "candidate": [],
            "deployment": [],
            "oracle": [],
        }
        for capability, source in sorted(graph.resolution.sources.items()):
            provenance = graph.provenance_of(capability)
            buckets[provenance].append((capability, source))
        return cls(
            candidate_owned=tuple(buckets["candidate"]),
            deployment_owned=tuple(buckets["deployment"]),
            oracle_owned=tuple(buckets["oracle"]),
        )

    def hashable(self) -> tuple[tuple[str, str], ...]:
        """The providers that belong in the execution fingerprint.

        Deployment and oracle, never candidate — a candidate's own
        provider is already in its id, and hashing it twice would split
        one candidate's episodes over two fingerprints for a change the
        identity already records.
        """
        return tuple(sorted(self.deployment_owned + self.oracle_owned))


@dataclass(frozen=True)
class CompatibilityReport:
    """Preflight's answer, in the shape an operator can act on."""

    state: RegistrationState
    missing_capabilities: tuple[str, ...] = ()
    missing_providers: tuple[str, ...] = ()
    missing_runtime: tuple[str, ...] = ()
    incompatible_action_types: tuple[str, ...] = ()
    incompatible_dynamics: tuple[str, ...] = ()
    incompatible_execution_models: tuple[str, ...] = ()
    fairness_refusals: tuple[str, ...] = ()
    graph_problems: tuple[str, ...] = ()
    provider_order: tuple[str, ...] = ()
    ownership: ProviderOwnership = field(default_factory=ProviderOwnership)
    adapter_chain: tuple[str, ...] = ()
    resolved_runtime_profile: dict = field(default_factory=dict)
    evidence_class: EvidenceClass = "production"

    @property
    def runnable(self) -> bool:
        return self.state == "registered_and_runnable"

    def host_conditions(self) -> HostConditions:
        """What this resolution contributes to the execution fingerprint."""
        return HostConditions(
            providers=self.ownership.hashable(),
            adapter_chain=self.adapter_chain,
            runtime_profile=dict(self.resolved_runtime_profile),
        )

    def explain(self) -> str:
        """One line naming every blocker, because fixing them one preflight
        at a time is the cost this report exists to avoid."""
        parts = []
        for label, values in (
            ("capabilities not offered by this deployment", self.missing_capabilities),
            ("capabilities nothing provides", self.missing_providers),
            ("runtime lane unavailable", self.missing_runtime),
            ("action types this host cannot drive", self.incompatible_action_types),
            ("robot dynamics this host cannot simulate", self.incompatible_dynamics),
            ("execution models this host cannot run", self.incompatible_execution_models),
            ("provenance the fairness policy refuses", self.fairness_refusals),
            ("provider graph", self.graph_problems),
        ):
            if values:
                parts.append(f"{label}: {list(values)}")
        return "; ".join(parts) or "runnable"


def resolve_compatibility(
    manifest: PluginManifest,
    *,
    available_capabilities: frozenset[str],
    graph: ProviderGraph | None = None,
    policy: FairnessPolicy | None = None,
    support: HostSupport | None = None,
    adapter_chain: tuple[str, ...] = (),
    missing_dependencies: tuple[str, ...] = (),
) -> CompatibilityReport:
    """Decide whether ``manifest`` can run here, and say why not.

    ``available_capabilities`` is what the deployment offers — its own
    grants plus whatever the resolved graph produces. Split from the
    graph because the two failures differ: a capability nobody offers is
    a deployment that has not been asked for it, while a capability
    offered but unproduced is a provider that is missing.
    """
    support = support or HostSupport()
    policy = policy or FairnessPolicy.production()

    produced = frozenset(graph.resolution.sources) if graph is not None else frozenset()
    offered = available_capabilities | produced

    missing_capabilities = manifest.requirements.missing_from(offered)
    missing_providers = tuple(
        capability
        for capability in manifest.requirements.all_of
        if capability in available_capabilities and capability not in offered
    )

    # **A lane whose dependencies are absent is not an available lane.**
    # ``missing_dependencies`` arrives from discovery, the only layer
    # that probes the interpreter, and is folded into the *runtime*
    # verdict rather than reported beside it: a report saying
    # ``registered_and_runnable`` next to a list of missing modules is
    # two conclusions about one plugin, and an operator has to guess
    # which one the platform will act on.
    lane_missing = (
        ()
        if manifest.runtime.production_lane in support.runtime_lanes
        else (manifest.runtime.production_lane,)
    )
    missing_runtime = lane_missing + tuple(f"module {name}" for name in missing_dependencies)

    incompatible_actions = _unsupported(manifest.supports.action_types, support.action_types)
    incompatible_dynamics = _unsupported(manifest.supports.robot_dynamics, support.robot_dynamics)
    incompatible_models = _unsupported(manifest.supports.execution_models, support.execution_models)

    graph_problems: tuple[str, ...] = ()
    ownership = ProviderOwnership()
    provenances: tuple[Provenance, ...] = ()
    order: tuple[str, ...] = ()
    if graph is not None:
        if not graph.resolution.runnable:
            graph_problems = (graph.resolution.explain(),)
        else:
            ownership = ProviderOwnership.from_graph(graph)
            order = graph.resolution.order
        provenances = graph.provenances()

    fairness_refusals = _fairness_refusals(policy, provenances)
    evidence_class = policy.evidence_class(provenances)

    state = _state(
        missing_capabilities=missing_capabilities,
        missing_providers=missing_providers,
        missing_runtime=missing_runtime,
        incompatible=incompatible_actions + incompatible_dynamics + incompatible_models,
        blocked=fairness_refusals + graph_problems,
    )

    return CompatibilityReport(
        state=state,
        missing_capabilities=missing_capabilities,
        missing_providers=missing_providers,
        missing_runtime=missing_runtime,
        incompatible_action_types=incompatible_actions,
        incompatible_dynamics=incompatible_dynamics,
        incompatible_execution_models=incompatible_models,
        fairness_refusals=fairness_refusals,
        graph_problems=graph_problems,
        provider_order=order,
        ownership=ownership,
        adapter_chain=adapter_chain,
        resolved_runtime_profile=_runtime_profile(manifest),
        evidence_class=evidence_class,
    )


def _unsupported(declared: tuple[str, ...], supported: frozenset[str]) -> tuple[str, ...]:
    """What the plugin needs and this host has not built.

    A plugin that lists several action types is saying it can work with
    any of them, so it is incompatible only when **none** is supported —
    reporting each unsupported entry of an otherwise-usable plugin would
    be a refusal made of alternatives it offered.
    """
    return () if set(declared) & supported else tuple(sorted(declared))


def _fairness_refusals(
    policy: FairnessPolicy, provenances: tuple[Provenance, ...]
) -> tuple[str, ...]:
    return tuple(sorted(set(provenances) - policy.admitted))


def _runtime_profile(manifest: PluginManifest) -> dict:
    """The production lane's profile, resolved.

    The *profile*, not the lane's name: a lane whose codec or deadline
    policy changed is a different execution condition even under the same
    word, and §5.9 rule 4 hashes what was resolved rather than what was
    called.
    """
    profile = manifest.runtime.profiles.get(manifest.runtime.production_lane)
    if profile is None:
        return {"lane": manifest.runtime.production_lane}
    return {"lane": manifest.runtime.production_lane, **profile.model_dump(mode="json")}


def _state(
    *,
    missing_capabilities: tuple[str, ...],
    missing_providers: tuple[str, ...],
    missing_runtime: tuple[str, ...],
    incompatible: tuple[str, ...],
    blocked: tuple[str, ...],
) -> RegistrationState:
    """One state, chosen so the name sends the reader to the right place.

    Order matters: an incompatible plugin is incompatible whatever else
    is missing — installing the provider it also lacks would not make an
    Ackermann plugin runnable on a differential-drive host, and telling
    someone to install it would waste their afternoon.
    """
    if incompatible:
        return "registered_but_incompatible"
    if missing_runtime:
        return "registered_but_missing_runtime"
    if missing_capabilities or missing_providers or blocked:
        return "registered_but_missing_provider"
    return "registered_and_runnable"
