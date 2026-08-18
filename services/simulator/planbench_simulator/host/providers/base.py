"""What a provider is: two phases, declared dependencies, no hidden state.

**The lifecycle is split on purpose** (plan §5.4, round-3 contract).
A tracker, a temporal grid and a filter all *must* carry state across
ticks, so "providers are stateless" was too strong. But if the single
method that produces a value also advances the state, then producing it
twice advances twice, and the only way to keep "two reads of one tick
agree" is to memoise — which makes the cache load-bearing for
correctness rather than a cost optimisation.

So:

- :meth:`advance` moves the state. The graph calls it **exactly once per
  tick**, and calling it twice for one tick is an error the graph
  raises, not a silent double-step.
- :meth:`read` is pure. Call it as often as you like; it must return the
  same thing until the next ``advance``.
- :meth:`reset` clears episode state. State may live *within* an
  episode; carrying it *between* episodes would leak one episode's
  perception into the next, which is the seed-independence assumption
  every paired comparison rests on.

Randomness comes from ``view.rng(stream, tick, index)`` — never from a
generator the provider keeps, because a kept generator makes the output
depend on how many times it was read.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from planbench_plugin_sdk import Cadence, Provenance

from planbench_simulator.host.runtime_view import ProviderRuntimeView


class ProviderError(RuntimeError):
    """A provider broke its own contract."""


class Provider(ABC):
    """One source of one channel."""

    #: Canonical capability this provider produces (a v1 token or a URI).
    capability: str
    #: How often it changes — decides the freshness invariant (§5.4).
    cadence: Cadence
    #: Who owns it. ``oracle`` taints the execution's evidence class and
    #: marks every channel ``sim_only``.
    provenance: Provenance
    #: Capabilities this provider consumes. The graph resolves these into
    #: a DAG; a provider only ever sees what it declared.
    depends_on: tuple[str, ...] = ()
    #: Stream id for addressable randomness. Distinct per provider so two
    #: providers drawing on one tick do not draw the same numbers.
    stream_id: int = 0

    def reset(self) -> None:  # noqa: B027 - optional by design, see below
        """Drop episode state. Default: nothing to drop.

        Deliberately concrete rather than abstract: a provider that
        derives its output from this tick's inputs alone has no state to
        clear, and forcing it to write an empty override would make the
        method that *matters* — a tracker's — look like the same
        boilerplate as one that does nothing.
        """

    @abstractmethod
    def advance(
        self,
        tick: int,
        now: float,
        view: ProviderRuntimeView,
        inputs: dict[str, Any],
    ) -> None:
        """Move this provider's state to ``tick``.

        ``inputs`` holds the payloads of ``depends_on``, already resolved
        by the graph in topological order.
        """

    @abstractmethod
    def read(self) -> Any:
        """The current payload. Pure: repeated calls must agree."""

    def revision(self) -> int | None:
        """Revision for ``on_change``/``static`` channels.

        Required for those cadences: an envelope that cannot say *which
        version* of the data it carries can only look fresh by
        re-stamping its timestamp, which is the lie the invariant exists
        to prevent. ``per_tick`` providers need none — the tick is the
        revision.
        """
        return None
