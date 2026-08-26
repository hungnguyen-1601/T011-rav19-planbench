"""The monolithic policies, wearing the same plugin contract.

Mechanically identical to :class:`LegacyLocalPlugin` — which is the
point: HĐ-4's second shape goes through the same loop and now the same
host, so a policy and a controller differ in what they *are*, never in
how they are mediated. The class exists so the role is named at the
type level and so the one policy-specific fact has somewhere to live:
the path in the reset request is dropped by ``MonolithicPolicy.reset``
itself, and this adapter must never grow a reason to look at it.
"""

from __future__ import annotations

from planbench_simulator.host.legacy_local import LegacyLocalPlugin


class LegacyPolicyPlugin(LegacyLocalPlugin):
    """One registered monolithic policy behind the host boundary."""
