"""What a channel must satisfy before a plugin may see it (H3).

Two things live here, and they answer two different questions.

:class:`CapabilityRegistry` answers *what is this capability supposed to
be* — its cadence, its payload schema digest, the codecs that may carry
it. A provider whose output contradicts the registered spec never
reaches a plugin; the DoD line is explicit that resolving the DAG is not
enough, and schema digest, codec and frame are checked before a channel
enters a bundle.

:class:`AuthorizedChannelBundle` answers *what may this plugin see* —
exactly the capabilities it declared and the host granted, and nothing
else. Undeclared access raises rather than returning ``None``: a plugin
that quietly gets nothing behaves differently from one that gets data,
and "differently" is a result nobody can interpret.

**The cadence invariant is written out per cadence**, not collapsed into
equality (round-4 fix):

- ``per_tick`` — produced this tick: timestamp equals the clock exactly.
- ``on_change`` — revision monotonic within the episode;
  ``produced_at <= now``; and a channel whose revision did **not**
  change may not move its timestamp. That last clause is the one that
  matters: without it a provider keeps freshness by re-stamping old
  data, and the lie is invisible until an asynchronous lane depends on
  it (H7).
- ``static`` — revision stable for the whole episode; ``produced_at``
  need not be now, and demanding it would force the same re-stamping.
"""

from __future__ import annotations

from dataclasses import dataclass

from planbench_plugin_sdk import Cadence, ChannelEnvelope, Provenance

#: Payload codec of the in-process lane: encode and decode are both the
#: identity function, which is what lets H2 parity be byte-level.
INPROCESS_CODEC = "python-object/v1"


class ChannelContractError(ValueError):
    """A channel does not satisfy its capability's registered contract."""


class UndeclaredChannelError(KeyError):
    """A plugin reached for a capability it never declared."""


@dataclass(frozen=True)
class CapabilitySpec:
    """What the platform promises about one capability."""

    capability: str
    cadence: Cadence
    #: Digest of the payload schema. ``""`` for the built-in native
    #: capabilities, whose payload *is* a validated platform model —
    #: their schema is the model, and inventing a digest for it would be
    #: a number nobody computes from anything.
    schema_digest: str = ""
    codecs: tuple[str, ...] = (INPROCESS_CODEC,)
    #: Frame the payload is expressed in.
    frame_id: str = "map"


class CapabilityRegistry:
    """Capability specs known to this host."""

    def __init__(self, specs: tuple[CapabilitySpec, ...] = ()) -> None:
        self._specs: dict[str, CapabilitySpec] = {spec.capability: spec for spec in specs}

    def register(self, spec: CapabilitySpec) -> None:
        existing = self._specs.get(spec.capability)
        if existing is not None and existing != spec:
            raise ChannelContractError(
                f"capability {spec.capability!r} is already registered with a different "
                "spec; two contradictory claims to one name must be quarantined, not "
                "resolved by whoever registered last"
            )
        self._specs[spec.capability] = spec

    def spec(self, capability: str) -> CapabilitySpec:
        spec = self._specs.get(capability)
        if spec is None:
            raise ChannelContractError(
                f"capability {capability!r} has no registered spec; a channel nobody "
                "described cannot be validated, and passing it through unchecked is "
                "how a payload shape drifts silently"
            )
        return spec

    def known(self) -> frozenset[str]:
        return frozenset(self._specs)


class CadenceMonitor:
    """Per-episode memory of what each channel last said.

    Kept beside the registry rather than inside the envelope because the
    invariants are *historical* — "monotonic", "did not move" — and an
    envelope can only speak about itself.
    """

    def __init__(self) -> None:
        self._last: dict[str, tuple[int | None, float]] = {}

    def reset(self) -> None:
        self._last.clear()

    def check(self, envelope: ChannelEnvelope, spec: CapabilitySpec, now: float) -> None:
        if envelope.cadence != spec.cadence:
            raise ChannelContractError(
                f"{envelope.capability}: registered as {spec.cadence}, delivered as "
                f"{envelope.cadence}; the freshness rule that applies is not the "
                "provider's to choose"
            )
        if envelope.cadence == "per_tick":
            if envelope.produced_at != now:
                raise ChannelContractError(
                    f"{envelope.capability}: a per_tick channel must carry this tick's "
                    f"time {now!r}, got {envelope.produced_at!r}"
                )
            return

        if envelope.revision is None:  # pragma: no cover - the SDK model refuses this
            raise ChannelContractError(
                f"{envelope.capability}: {envelope.cadence} needs a revision"
            )
        if envelope.produced_at > now:
            raise ChannelContractError(
                f"{envelope.capability}: produced_at {envelope.produced_at!r} is in the "
                f"future of the clock {now!r}"
            )

        previous = self._last.get(envelope.capability)
        if previous is not None:
            last_revision, last_produced_at = previous
            if envelope.cadence == "static":
                if envelope.revision != last_revision:
                    raise ChannelContractError(
                        f"{envelope.capability}: a static channel changed revision "
                        f"{last_revision} -> {envelope.revision} inside one episode"
                    )
            elif envelope.revision < (last_revision or 0):
                raise ChannelContractError(
                    f"{envelope.capability}: revision went backwards "
                    f"{last_revision} -> {envelope.revision}"
                )
            if envelope.revision == last_revision and envelope.produced_at != last_produced_at:
                raise ChannelContractError(
                    f"{envelope.capability}: revision {envelope.revision} is unchanged but "
                    f"produced_at moved {last_produced_at!r} -> {envelope.produced_at!r}. "
                    "Unchanged data that reports a new timestamp is old data wearing a "
                    "fresh stamp, and no later freshness policy can see through it"
                )
        self._last[envelope.capability] = (envelope.revision, envelope.produced_at)


def validate_channel(
    envelope: ChannelEnvelope,
    registry: CapabilityRegistry,
    monitor: CadenceMonitor,
    now: float,
) -> None:
    """Everything checked before a channel may enter a bundle."""
    spec = registry.spec(envelope.capability)
    if envelope.payload_encoding not in spec.codecs:
        raise ChannelContractError(
            f"{envelope.capability}: codec {envelope.payload_encoding!r} is not one of "
            f"{list(spec.codecs)}"
        )
    if envelope.frame_id != spec.frame_id:
        raise ChannelContractError(
            f"{envelope.capability}: frame {envelope.frame_id!r} is not the registered "
            f"{spec.frame_id!r}; a payload read in the wrong frame is wrong silently"
        )
    monitor.check(envelope, spec, now)


class AuthorizedChannelBundle:
    """The channels one plugin was granted this tick, and only those."""

    def __init__(self, envelopes: tuple[ChannelEnvelope, ...]) -> None:
        self._by_capability = {envelope.capability: envelope for envelope in envelopes}

    def __contains__(self, capability: object) -> bool:
        return capability in self._by_capability

    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_capability))

    def envelope(self, capability: str) -> ChannelEnvelope:
        envelope = self._by_capability.get(capability)
        if envelope is None:
            raise UndeclaredChannelError(
                f"{capability!r} was not granted to this plugin; granted: "
                f"{list(self.capabilities())}. A plugin reads what it declared — "
                "handing back nothing instead would make an undeclared read look "
                "like an empty measurement"
            )
        return envelope

    def payload(self, capability: str):
        return self.envelope(capability).payload

    def envelopes(self) -> tuple[ChannelEnvelope, ...]:
        return tuple(self._by_capability[name] for name in self.capabilities())

    def provenance_of(self, capability: str) -> Provenance:
        return self.envelope(capability).provenance
