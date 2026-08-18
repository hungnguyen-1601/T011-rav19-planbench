"""Which sources a run may use, and what its evidence is worth (§5.10).

Two rules, and they are different in kind.

**Admission** — may this provenance appear at all in this run? A
production benchmark refuses oracle sources outright: an episode fed
ground truth measures an upper bound, not a deployable candidate, and
the point of refusing at admission is that nobody spends three hundred
episodes discovering it afterwards. A research run admits everything and
carries the consequence in its evidence class.

**Evidence class** — what may be concluded from what did run. Resolved,
never declared: the entry has a class (a D12 reference adapter is a
reference *by construction*, which no provider graph can tell you), the
provider graph has a class (oracle if any source is oracle), and the
execution takes the **meet** of the two under
``production > reference > oracle``. A production stack fed one oracle
channel yields oracle evidence, and nobody has to remember to say so.

``benchmarkable`` is deliberately absent here. The round-4 split names
two gates — ``production_eligible`` for the entry, resolved
``evidence_class`` for the execution — and production scoring needs
both; one boolean spanning them is what made ``benchmarkable`` mean two
things and grow a ``withdrawn`` field to disambiguate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from planbench_plugin_sdk import Provenance

EvidenceClass = Literal["production", "reference", "oracle"]

#: Most to least authoritative. ``meet`` takes the least.
_ORDER: tuple[EvidenceClass, ...] = ("production", "reference", "oracle")

#: Provenance that makes an execution's evidence oracle-grade, and marks
#: every channel it produced ``sim_only``.
ORACLE_PROVENANCE: Provenance = "oracle"


class FairnessViolation(ValueError):
    """A run used a source its policy does not admit."""


def meet(*classes: EvidenceClass) -> EvidenceClass:
    """The least authoritative of the given classes."""
    return max(classes, key=_ORDER.index) if classes else "production"


def provenance_class(provenances: tuple[Provenance, ...]) -> EvidenceClass:
    """What a provider graph alone implies.

    Only ``oracle`` demotes. ``candidate`` and ``deployment`` are both
    legitimate production sources — the difference between them is an
    *ownership* question that decides whose identity changes and who is
    charged for the compute (§5.9, §7.1), not an evidence question.
    """
    return "oracle" if ORACLE_PROVENANCE in provenances else "production"


@dataclass(frozen=True)
class FairnessPolicy:
    """What one run admits, and what it concludes."""

    #: Provenances this run may use at all.
    admitted: frozenset[Provenance] = frozenset({"deployment", "candidate"})
    #: The entry's own class, before any provider is considered.
    entry_class: EvidenceClass = "production"

    @classmethod
    def production(cls, entry_class: EvidenceClass = "production") -> FairnessPolicy:
        """No oracle sources; the ordinary benchmark policy."""
        return cls(admitted=frozenset({"deployment", "candidate"}), entry_class=entry_class)

    @classmethod
    def research(cls) -> FairnessPolicy:
        """Everything admitted, evidence demoted accordingly — the lane
        that lets an oracle upper bound be measured through the same
        runtime instead of a script beside it (P4/P5 had no such lane)."""
        return cls(admitted=frozenset({"deployment", "candidate", "oracle"}), entry_class="oracle")

    def admit(self, provenances: tuple[Provenance, ...]) -> None:
        refused = sorted(set(provenances) - self.admitted)
        if refused:
            raise FairnessViolation(
                f"this run does not admit provenance {refused}; admitted: "
                f"{sorted(self.admitted)}. An oracle source measures an upper bound, "
                "so refusing it here costs nothing and discovering it after three "
                "hundred episodes costs the run"
            )

    def evidence_class(self, provenances: tuple[Provenance, ...]) -> EvidenceClass:
        """The execution's class: entry meets provider graph."""
        return meet(self.entry_class, provenance_class(provenances))

    def is_sim_only(self, provenance: Provenance) -> bool:
        """Whether a channel from this source may never be claimed of real
        hardware. True exactly for oracle sources."""
        return provenance == ORACLE_PROVENANCE
