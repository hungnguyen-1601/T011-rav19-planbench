"""One control tick's cost, split six ways (§5.9).

**Every layer is a measurement of a named thing, and the remainder has
its own name.** The first version of this computed transport as
"end-to-end minus what the plugin said it spent", which quietly folded
queueing, worker dispatch and everything unclassified into a number
labelled *transport*. A layer that absorbs whatever is left over is not
a measurement, it is a residual wearing a measurement's name — and a
reader diagnosing a slow candidate would go looking at the codec.

So transport is timed directly (encode, write, wait, read, decode) and
:attr:`host_overhead_ms` is the **declared** remainder: the part the
host spent that no other layer claims. It can be read as "how much of
this tick nobody has accounted for", which is a useful number precisely
because it is not hidden inside a plausible one.

**``end_to_end_control_ms`` is the whole tick.** From the host deciding
to ask for a command to the host holding a validated action: providers,
transport, the algorithm, the action adapter, and the host's own work.
Anything narrower must not be called end-to-end, because a deadline gate
reading it would pass on a budget it never measured — the exact failure
the plan's §5.9 rule 5 exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Who measured a layer, and therefore whether a gate may read it
#: (§5.9 rule 6).
HOST_MEASURED = "host"
PLUGIN_REPORTED = "plugin"

#: The six layers, in the order the plan names them. Also the trace
#: column order, so a reader of either sees the same decomposition.
LATENCY_LAYERS: tuple[str, ...] = (
    "shared_provider_ms",
    "candidate_provider_ms",
    "transport_ms",
    "algorithm_compute_ms",
    "action_adapter_ms",
    "host_overhead_ms",
)


@dataclass
class LatencyLedger:
    """The six layers of one tick, plus who measured the compute."""

    shared_provider_ms: float = 0.0
    candidate_provider_ms: float = 0.0
    transport_ms: float = 0.0
    algorithm_compute_ms: float = 0.0
    action_adapter_ms: float = 0.0
    host_overhead_ms: float = 0.0
    #: ``host`` in-process, ``plugin`` across a process boundary. A gate
    #: must not read ``algorithm_compute_ms`` when this says ``plugin``.
    compute_measured_by: str = HOST_MEASURED

    @property
    def candidate_path_ms(self) -> float:
        """What the candidate is charged for (§5.9)."""
        return (
            self.candidate_provider_ms
            + self.transport_ms
            + self.algorithm_compute_ms
            + self.action_adapter_ms
        )

    @property
    def end_to_end_control_ms(self) -> float:
        """The whole tick — the only figure a deadline gate may read."""
        return self.shared_provider_ms + self.candidate_path_ms + self.host_overhead_ms

    def account_for(self, total_ms: float) -> None:
        """Assign the unclaimed part of ``total_ms`` to host overhead.

        Clamped at zero: a plugin reporting more compute than the tick
        took is reporting something impossible, and a negative overhead
        would launder that into a plausible total.
        """
        claimed = self.end_to_end_control_ms - self.host_overhead_ms
        self.host_overhead_ms = max(0.0, total_ms - claimed)

    def as_row(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in LATENCY_LAYERS}

    def as_trace_row(self) -> dict[str, float | str]:
        """The six columns plus who measured the compute.

        The provenance travels **with** the number rather than in a
        sidecar: a gate reading ``algorithm_compute_ms`` without knowing
        the plugin supplied it is the exact mistake §5.9 rule 6 forbids,
        and the way to make that hard is to put the answer in the same
        row.
        """
        return {**self.as_row(), "compute_measured_by": self.compute_measured_by}


@dataclass
class LayerTimer:
    """Accumulates one tick's layers as they are measured."""

    ledger: LatencyLedger = field(default_factory=LatencyLedger)

    def reset(self) -> None:
        self.ledger = LatencyLedger()
