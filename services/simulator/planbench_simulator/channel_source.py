"""The one seam the loop offers a data plane it knows nothing about.

``run_stack`` drives controllers through two ABCs and has never known
where their inputs come from. A channel-native plugin needs more: its
inputs are produced by a provider graph that must be advanced once per
control tick, against an engine only this loop owns.

**One seam, plugin-agnostic, and that is the whole design.** The
alternative — a branch in the loop per algorithm — is the coupling the
plan's second rejected alternative names (§12), and it is what makes
"adding a plugin does not touch the loop" false. This protocol is
implemented once, in the host; the loop calls two methods and never
learns what a provider is.

Absent, the loop behaves exactly as it did: ``None`` is not a special
case to remember but the ordinary state of every legacy stack, and the
parity fixture is what says so.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ChannelSource(Protocol):
    """Whatever produces a plugin's inputs, driven by the loop's clock."""

    def bind(self, engine: Any, planning_grid: Any, episode_seed: int) -> None:
        """Attach to one episode, before the first control tick."""

    def advance(self) -> None:
        """Move to the current tick. Called once per control decision."""
