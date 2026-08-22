"""Three enums that are constantly mistaken for one another, kept apart.

A checker result answers three separate questions, and the bug this
module exists to prevent is answering them with one word ``pass``:

``execution_status``
    did the tool *run*? ``completed`` | ``rejected`` | ``failed`` |
    ``not_checkable``. ``not_checkable`` is a fact about the world —
    the inputs needed to check simply are not recorded — not a fact
    about the proposition.
``proposition_verdict``
    did the proposition *stand*? ``supported`` | ``refuted`` |
    ``inconclusive``. A tool that completes and refutes the hypothesis
    is a fully successful run and a dead claim; one word cannot carry
    both readings.
``input_provenance``
    where did the inputs come from? ``recorded`` |
    ``verified_reconstruction`` | ``reconstructed`` | ``missing``.

**One provenance vocabulary for the whole system.** Earlier drafts wrote
``recorded_or_verified_reconstruction`` as a single token, which reads
as a fifth value and then has to be special-cased everywhere it is
compared. It is two values, and the tool cards say which ones they
accept. ``not_checkable`` is *not* a provenance — a run that could not
be checked has an execution status, not an input pedigree.

**The ceiling table is the whole point.** Replaying a planner over
inputs nobody recorded is a plausible-looking exercise that proves
nothing about the run being explained, so ``reconstructed`` caps at
``associated`` no matter how strong the tool is; the entire existing
trace store is in that bucket until the E4.5 sidecar writer ships.
"""

from __future__ import annotations

from typing import Literal

from planbench_explanation.levels import ClaimLevel

ExecutionStatus = Literal["completed", "rejected", "failed", "not_checkable"]

EXECUTION_STATUSES: tuple[ExecutionStatus, ...] = (
    "completed",
    "rejected",
    "failed",
    "not_checkable",
)

PropositionVerdict = Literal["supported", "refuted", "inconclusive"]

PROPOSITION_VERDICTS: tuple[PropositionVerdict, ...] = (
    "supported",
    "refuted",
    "inconclusive",
)

InputProvenance = Literal["recorded", "verified_reconstruction", "reconstructed", "missing"]

INPUT_PROVENANCES: tuple[InputProvenance, ...] = (
    "recorded",
    "verified_reconstruction",
    "reconstructed",
    "missing",
)

#: The strongest claim each provenance can ever support. ``missing`` has
#: no entry on purpose — see :func:`provenance_ceiling`.
_PROVENANCE_CEILING: dict[InputProvenance, ClaimLevel] = {
    "recorded": "intervention_supported",
    "verified_reconstruction": "intervention_supported",
    "reconstructed": "associated",
}


class MissingInputEvidence(ValueError):
    """A check was scored on inputs that do not exist."""


def provenance_ceiling(provenance: InputProvenance) -> ClaimLevel:
    """Strongest level the inputs allow, independent of the tool.

    ``missing`` raises instead of returning ``observed``: there is no
    level for "we checked nothing", and returning the weakest one would
    let an unbacked check contribute a row to the ledger.
    """
    try:
        return _PROVENANCE_CEILING[provenance]
    except KeyError as exc:
        raise MissingInputEvidence(
            f"input provenance {provenance!r} supports no claim at any level; "
            "a checker with missing inputs must report execution_status "
            "'not_checkable' rather than a verdict"
        ) from exc
