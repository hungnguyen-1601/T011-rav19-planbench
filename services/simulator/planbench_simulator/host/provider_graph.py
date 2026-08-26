"""Resolving providers into a DAG, and walking it once per tick (H3).

The graph answers three questions and refuses to guess at any of them.

**Which provider supplies a capability?** Exactly one. Two providers
offering one capability without an explicit selection is *ambiguous* and
fails resolution — the host never picks the "better" source, because
``human_state_estimates`` from a deployment tracker and from ground
truth are different benchmark conditions, and choosing between them
silently would change what a result means.

**Can everything be produced?** A declared dependency with no provider
is reported by name, together with who wanted it. A cycle is reported as
the cycle, not as a recursion error at some arbitrary entry point.

**In what order?** Topological. The round-3 contract says a provider's
output must not depend on the order the graph walked it in *among
providers that do not depend on each other*; among those that do, the
DAG order is exactly the dependency the declaration asked for.

Per-tick caching lives here rather than in providers, and it is a cost
optimisation only: :meth:`Provider.read` is pure by contract, so
dropping the cache would change the bill, never the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planbench_plugin_sdk import ChannelEnvelope

from planbench_simulator.host.channel_bundle import (
    INPROCESS_CODEC,
    AuthorizedChannelBundle,
    CadenceMonitor,
    CapabilityRegistry,
    validate_channel,
)
from planbench_simulator.host.providers.base import Provider, ProviderError
from planbench_simulator.host.runtime_view import ProviderRuntimeView


class ProviderGraphError(ValueError):
    """The declared providers do not form a runnable graph."""


@dataclass(frozen=True)
class GraphResolution:
    """What resolution decided — the preflight-facing answer (feeds H4)."""

    order: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    ambiguous: tuple[str, ...] = ()
    cycles: tuple[str, ...] = ()
    #: capability -> provider class name, so a report can say which
    #: source produced a channel rather than only that one did.
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def runnable(self) -> bool:
        return not (self.missing or self.ambiguous or self.cycles)

    def explain(self) -> str:
        parts = []
        if self.missing:
            parts.append(f"missing providers for {list(self.missing)}")
        if self.ambiguous:
            parts.append(f"ambiguous capabilities {list(self.ambiguous)}")
        if self.cycles:
            parts.append(f"dependency cycle through {list(self.cycles)}")
        return "; ".join(parts) or "runnable"


class ProviderGraph:
    """Providers, resolved once and advanced once per tick."""

    def __init__(
        self,
        providers: tuple[Provider, ...],
        registry: CapabilityRegistry,
        *,
        selection: dict[str, str] | None = None,
    ) -> None:
        """``selection`` maps capability -> provider class name, the
        explicit tie-break the host refuses to invent. Absent it, a
        contested capability stays ambiguous."""
        self._providers = providers
        self._registry = registry
        self._selection = dict(selection or {})
        self._monitor = CadenceMonitor()
        self._payloads: dict[str, object] = {}
        self._revisions: dict[str, int | None] = {}
        #: capability -> (revision, when that revision was first stamped)
        self._stamps: dict[str, tuple[int | None, float]] = {}
        self._advanced_tick: int | None = None
        self.resolution = self._resolve()

    # -- resolution ----------------------------------------------------

    def _resolve(self) -> GraphResolution:
        offers: dict[str, list[Provider]] = {}
        for provider in self._providers:
            offers.setdefault(provider.capability, []).append(provider)

        ambiguous: list[str] = []
        chosen: dict[str, Provider] = {}
        for capability, candidates in offers.items():
            if len(candidates) == 1:
                chosen[capability] = candidates[0]
                continue
            wanted = self._selection.get(capability)
            picked = [p for p in candidates if type(p).__name__ == wanted]
            if len(picked) == 1:
                chosen[capability] = picked[0]
            else:
                ambiguous.append(capability)

        missing = sorted(
            {
                dependency
                for provider in self._providers
                for dependency in provider.depends_on
                if dependency not in offers
            }
        )

        cycles = self._find_cycle(chosen)
        order = () if (missing or ambiguous or cycles) else self._topological(chosen)
        self._chosen = chosen
        return GraphResolution(
            order=order,
            missing=tuple(missing),
            ambiguous=tuple(sorted(ambiguous)),
            cycles=tuple(cycles),
            sources={cap: type(p).__name__ for cap, p in chosen.items()},
        )

    def _find_cycle(self, chosen: dict[str, Provider]) -> tuple[str, ...]:
        """The capabilities on one cycle, or empty. Reported as the cycle
        because "maximum recursion depth" names the symptom, not the two
        providers that each wait for the other."""
        colour: dict[str, int] = {}
        stack: list[str] = []

        def visit(capability: str) -> tuple[str, ...]:
            if colour.get(capability) == 1:
                return tuple(stack[stack.index(capability) :])
            if colour.get(capability) == 2 or capability not in chosen:
                return ()
            colour[capability] = 1
            stack.append(capability)
            for dependency in chosen[capability].depends_on:
                found = visit(dependency)
                if found:
                    return found
            stack.pop()
            colour[capability] = 2
            return ()

        for capability in sorted(chosen):
            found = visit(capability)
            if found:
                return found
        return ()

    def _topological(self, chosen: dict[str, Provider]) -> tuple[str, ...]:
        order: list[str] = []
        seen: set[str] = set()

        def visit(capability: str) -> None:
            if capability in seen or capability not in chosen:
                return
            seen.add(capability)
            for dependency in sorted(chosen[capability].depends_on):
                visit(dependency)
            order.append(capability)

        for capability in sorted(chosen):
            visit(capability)
        return tuple(order)

    # -- episode lifecycle ---------------------------------------------

    def reset(self) -> None:
        """Start an episode: every provider drops its state, and so does
        the cadence history — a revision carried over from the previous
        episode would make this one's first channel look stale."""
        for provider in self._providers:
            provider.reset()
        self._monitor.reset()
        self._payloads.clear()
        self._revisions.clear()
        self._stamps.clear()
        self._advanced_tick = None

    def advance(self, tick: int, now: float, view: ProviderRuntimeView) -> None:
        """Walk the DAG once. Exactly once per tick, enforced."""
        if not self.resolution.runnable:
            raise ProviderGraphError(
                f"this provider graph is not runnable: {self.resolution.explain()}"
            )
        if self._advanced_tick == tick:
            raise ProviderError(
                f"the graph was already advanced for tick {tick}; advancing twice would "
                "step every stateful provider twice for one tick of the world. Read "
                "again instead — read() is pure by contract"
            )
        for capability in self.resolution.order:
            provider = self._chosen[capability]
            inputs = {name: self._payloads[name] for name in provider.depends_on}
            provider.advance(tick, now, view, inputs)
            self._payloads[capability] = provider.read()
            self._revisions[capability] = provider.revision()
        self._advanced_tick = tick

    # -- granting ------------------------------------------------------

    def bundle_for(
        self, granted: tuple[str, ...], now: float, *, tick: int | None = None
    ) -> AuthorizedChannelBundle:
        """Wrap the granted capabilities as validated envelopes.

        Every envelope goes through schema/codec/frame/cadence validation
        before the bundle exists, so a plugin cannot be the first thing to
        notice that a provider's output contradicts its capability.
        """
        del tick  # the clock is the per_tick authority; the tick is its index
        envelopes: list[ChannelEnvelope] = []
        for capability in granted:
            if capability not in self._payloads:
                raise ProviderGraphError(
                    f"capability {capability!r} was granted but nothing produced it this "
                    f"tick; produced: {sorted(self._payloads)}"
                )
            provider = self._chosen[capability]
            spec = self._registry.spec(capability)
            produced_at = (
                now if provider.cadence == "per_tick" else self._produced_at(capability, now)
            )
            envelope = ChannelEnvelope(
                capability=capability,
                cadence=provider.cadence,
                revision=self._revisions[capability],
                produced_at=produced_at,
                frame_id=spec.frame_id,
                provenance=provider.provenance,
                payload_encoding=INPROCESS_CODEC,
                payload=self._payloads[capability],
            )
            validate_channel(envelope, self._registry, self._monitor, now)
            envelopes.append(envelope)
        return AuthorizedChannelBundle(tuple(envelopes))

    def _produced_at(self, capability: str, now: float) -> float:
        """When this revision of a non-per-tick channel was first seen.

        The host stamps it, not the provider, and it does not move while
        the revision does not — which is the same rule the monitor
        enforces, applied at the source so the honest path is the easy
        one.
        """
        revision = self._revisions[capability]
        previous = self._stamps.get(capability)
        if previous is None or previous[0] != revision:
            self._stamps[capability] = (revision, now)
        return self._stamps[capability][1]

    def provenances(self) -> tuple[str, ...]:
        """Every provenance the resolved graph carries — the input of the
        fairness verdict (§5.10)."""
        return tuple(sorted({provider.provenance for provider in self._chosen.values()}))

    def provenance_of(self, capability: str) -> str:
        """Who owns one resolved capability — the input of the ownership
        split that decides whether a change moves ``candidate_id`` or the
        execution fingerprint (§7.1)."""
        provider = self._chosen.get(capability)
        if provider is None:
            raise ProviderGraphError(
                f"capability {capability!r} is not in the resolved graph; resolved: "
                f"{sorted(self._chosen)}"
            )
        return provider.provenance
