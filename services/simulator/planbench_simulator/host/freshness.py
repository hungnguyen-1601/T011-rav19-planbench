"""Freshness policy for channels that arrive late (H7).

H3 built the *invariant*: what a channel may claim about itself, per
cadence, in a synchronous world where every producer runs inside the
tick it belongs to. It deliberately stopped there, because a tolerance
with nothing asynchronous to tolerate is a validation surface that never
fires and a false sense that lateness was handled.

The subprocess lane makes lateness real, so the policy arrives with it.
Four decisions, and each is a decision rather than a default:

**How old is too old.** ``max_age_s`` per cadence. A ``per_tick``
channel that missed its tick is *stale*, and the question is what to
give the plugin instead of it.

**Reuse or drop.** Reusing the previous value is what a real robot's
message bus does, and it is honest only if the plugin can tell: a reused
envelope keeps its **original** ``produced_at`` and revision, so a
plugin computing an age gets the true one. Dropping hands the plugin
nothing and lets it decide — correct for a plugin that would rather
brake than act on a guess, and the reason ``drop`` is not merely
``reuse`` with an expiry.

**Out of order.** A revision older than one already delivered is
discarded, never delivered "for completeness". Feeding a plugin a
regression in a quantity it has been told is monotonic is worse than
feeding it nothing.

**Clock skew.** A timestamp slightly ahead of the host clock is a clock
difference, not a message from the future, and rejecting it would make
a working system look broken. Beyond the tolerance it is a fault and is
refused — the tolerance is declared so that "slightly" is a number
somebody chose rather than a habit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from planbench_plugin_sdk import Cadence, ChannelEnvelope

StalePolicy = Literal["reuse", "drop", "fail"]


@dataclass(frozen=True)
class FreshnessPolicy:
    """What to do with a channel that did not arrive on time."""

    #: Oldest a channel of each cadence may be, in seconds. ``None``
    #: means no limit, which is the honest setting for ``static``.
    max_age_s: dict[Cadence, float | None] = field(
        default_factory=lambda: {"per_tick": 0.15, "on_change": 2.0, "static": None}
    )
    on_stale: StalePolicy = "reuse"
    #: How far ahead of the host clock a timestamp may be before it is a
    #: fault rather than a clock difference.
    clock_skew_tolerance_s: float = 0.01

    def age_limit(self, cadence: Cadence) -> float | None:
        return self.max_age_s.get(cadence)


class StaleChannelError(ValueError):
    """A late channel under a policy that refuses to guess."""


@dataclass
class FreshnessFilter:
    """Applies a :class:`FreshnessPolicy` across one episode.

    Stateful on purpose: "out of order" and "reuse the previous value"
    are both statements about history, and an envelope can only speak
    about itself.
    """

    policy: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    _last: dict[str, ChannelEnvelope] = field(default_factory=dict)
    #: Counted rather than logged: an episode where a third of the ticks
    #: ran on reused data is a different measurement from one where none
    #: did, and a reader has no other way to tell.
    stats: dict[str, int] = field(
        default_factory=lambda: {"delivered": 0, "reused": 0, "dropped": 0, "out_of_order": 0}
    )

    def reset(self) -> None:
        self._last.clear()
        for key in self.stats:
            self.stats[key] = 0

    def admit(self, envelope: ChannelEnvelope, now: float) -> ChannelEnvelope | None:
        """The envelope a plugin should see, or ``None`` to withhold it."""
        if envelope.produced_at > now + self.policy.clock_skew_tolerance_s:
            raise StaleChannelError(
                f"{envelope.capability}: produced_at {envelope.produced_at!r} is "
                f"{envelope.produced_at - now:.3f}s ahead of the clock, beyond the "
                f"{self.policy.clock_skew_tolerance_s:.3f}s skew tolerance"
            )

        previous = self._last.get(envelope.capability)
        if (
            previous is not None
            and envelope.revision is not None
            and previous.revision is not None
            and envelope.revision < previous.revision
        ):
            self.stats["out_of_order"] += 1
            return self._fallback(previous, envelope)

        limit = self.policy.age_limit(envelope.cadence)
        if limit is not None and now - envelope.produced_at > limit:
            return self._fallback(previous, envelope)

        self._last[envelope.capability] = envelope
        self.stats["delivered"] += 1
        return envelope

    def _fallback(
        self, previous: ChannelEnvelope | None, envelope: ChannelEnvelope
    ) -> ChannelEnvelope | None:
        if self.policy.on_stale == "fail":
            raise StaleChannelError(
                f"{envelope.capability} is stale and this policy does not substitute; "
                "a run that silently swapped in older data would report a fidelity it "
                "did not have"
            )
        if self.policy.on_stale == "reuse" and previous is not None:
            # The *previous envelope*, unmodified: its produced_at is the
            # truth about when this data was made, and re-stamping it to
            # look current is the exact lie the cadence invariant forbids.
            self.stats["reused"] += 1
            return previous
        self.stats["dropped"] += 1
        return None
