"""The channel envelope: how one piece of granted data arrives (plan §5.3).

A plugin never touches the engine; it receives envelopes for exactly the
capabilities it declared and was granted. The envelope carries enough to
audit the data without decoding it: which capability, produced when and
in which frame, owned by whom, encoded how.

**Cadence decides the freshness invariant** (plan §5.4, round-4 fix):

- ``per_tick`` — produced this tick; timestamp equals the current
  simulation time, exactly.
- ``on_change`` — produced when something changed (a replan, a costmap
  update); carries a **revision** that must be monotonic within the
  episode, and a ``produced_at`` timestamp that must never be re-stamped
  to look current. A global path consumed for three hundred ticks is
  *old and valid*, and the envelope must be allowed to say so.
- ``static`` — produced once per episode; revision stable.

The host enforces monotonicity and the per-tick equality; the schema here
enforces what a single envelope can state about itself — ``on_change``
and ``static`` without a revision are refused at construction, because a
revision added later would be exactly the re-stamping the rule forbids.

``provenance`` is load-bearing for fairness: ``human-state-estimates``
from a deployment tracker, from a candidate's own estimator and from the
engine's ground truth are three different benchmark conditions, and §5.10
resolves the execution's evidence class from this field.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from planbench_plugin_sdk.capabilities import canonical_requirement

Cadence = Literal["per_tick", "on_change", "static"]

Provenance = Literal["deployment", "candidate", "oracle"]


class ChannelEnvelope(BaseModel):
    """One granted channel, one delivery."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: str
    cadence: Cadence
    produced_at: float
    frame_id: str = "map"
    provenance: Provenance
    #: Monotonic within an episode; required for every cadence that may
    #: legitimately deliver the same payload across many ticks.
    revision: int | None = None
    payload_encoding: str = "python-object/v1"
    payload: Any = None

    @model_validator(mode="after")
    def _validate(self) -> ChannelEnvelope:
        canonical = canonical_requirement(self.capability)
        if canonical != self.capability:
            raise ValueError(
                f"channel capability must be canonical: {self.capability!r} "
                f"should be spelled {canonical!r}"
            )
        if self.cadence in ("on_change", "static") and self.revision is None:
            raise ValueError(
                f"a {self.cadence} channel needs a revision: without one, the only "
                "way to look fresh is to re-stamp produced_at, which is the lie the "
                "cadence invariant exists to forbid"
            )
        return self
