"""The model-free answer for one episode, and the bar a model has to clear.

The run-level floor walks the packet's observations and proposes what
each one is consistent with. That reading does not transfer: an
observation there is a pattern over thirty episodes, and here there is
one episode and two sides of it.

So this floor answers in the two registers the packet keeps apart:

* a **diagnosis** for every detection, on whichever candidate it fired —
  what happened, said plainly, with no claim about the outcome;
* a **contrast** only where :mod:`episode_packet` already found a
  difference with support behind it, and only when the polarity agrees.

Neither register invents anything the packet does not carry, and the
sentences hold no numbers: the figures are in the packet, and the refs
point at them. That rule is why the run-level floor once abstained on
every packet that had anything in it — it wrote "in 9 of 30 episodes"
into a statement, and the guard drops a quantity in a statement no
matter who wrote it.
"""

from __future__ import annotations

from planbench_explanation.episode_packet import (
    EpisodeContrast,
    EpisodePacket,
)
from planbench_explanation.ledger import EvidenceRef, HypothesisProposal
from planbench_explanation.propositions import PropositionType, effect_direction

#: What a floor proposal is offered as. The same word the analyst's own
#: annotation carries, so a harness scores the two on one scale.
Bearing = str

DIAGNOSIS: Bearing = "diagnosis"
CONTRAST: Bearing = "contrast"


class EpisodeFloorAnswer:
    """The floor's proposals, each with the register it was offered in.

    A plain object rather than an ``AnalysisResponse``: the response is
    the wire contract an external analyst answers on, and it has no room
    for a bearing. Putting one there would widen a frozen schema to
    record something only this scope asks about — the same reason the
    analyst's own annotations travel beside its response rather than
    inside it.
    """

    __slots__ = ("bearings", "proposals")

    def __init__(
        self,
        proposals: tuple[HypothesisProposal, ...],
        bearings: dict[str, Bearing],
    ) -> None:
        self.proposals = proposals
        self.bearings = bearings

    @property
    def abstained(self) -> bool:
        return not self.proposals

    def of(self, bearing: Bearing) -> tuple[HypothesisProposal, ...]:
        return tuple(
            proposal
            for proposal in self.proposals
            if self.bearings.get(proposal.hypothesis_id) == bearing
        )


def _statement_for_diagnosis(detection_type: str, candidate_id: str) -> str:
    return f"{detection_type.replace('_', ' ')} was detected on {candidate_id} in this episode"


def _statement_for_contrast(contrast: EpisodeContrast, proposition: PropositionType) -> str:
    mechanism = proposition.replace("_", " ")
    if contrast.kind == "detection_only_on_loser":
        return (
            f"a pattern present on {contrast.against_candidate_id} and absent on the other "
            f"side is consistent with {mechanism}"
        )
    return (
        f"a pattern worse on {contrast.against_candidate_id} than on the other side is "
        f"consistent with {mechanism}"
    )


def episode_floor(packet: EpisodePacket) -> EpisodeFloorAnswer:
    """What can be said about this episode without asking a model.

    Abstains — proposes nothing at all — when there is neither a
    detection to report nor a difference to offer. That is the right
    answer on an episode where both stacks simply drove to the goal, and
    it is the reason this floor is worth keeping: an analyst that cannot
    beat "say what fired, and offer a difference only where one was
    found" is not adding anything a filter could not.
    """
    blocked = set(packet.blocked_claim_types)
    proposals: list[HypothesisProposal] = []
    bearings: dict[str, Bearing] = {}

    index = 0
    for diagnosis in packet.diagnoses:
        for detection in diagnosis.detections:
            index += 1
            hypothesis_id = f"floor-diag-{index:03d}"
            proposals.append(
                HypothesisProposal(
                    hypothesis_id=hypothesis_id,
                    hypothesis_statement=_statement_for_diagnosis(
                        detection.type, diagnosis.candidate_id
                    ),
                    # A diagnosis names no mechanism and blames no
                    # component: it reports that a detector fired. The
                    # proposition below is the weakest assertable one
                    # that carries the observation, and the subject is
                    # the geometry of the task rather than either stack
                    # — nothing here attributes anything to a candidate.
                    proposition_type="component_specific_attribution",
                    proposed_subject="task_geometry",
                    supports=(
                        EvidenceRef(
                            ref=(
                                f"obs:{detection.type}:{diagnosis.candidate_id}"
                                f"@{packet.episode_context_id}"
                            ),
                            kind="observation",
                        ),
                    ),
                )
            )
            bearings[hypothesis_id] = DIAGNOSIS

    for position, contrast in enumerate(packet.contrasts, start=1):
        if contrast.strength != "support" or contrast.proposition_type is None:
            continue
        proposition = contrast.proposition_type
        if proposition in blocked:
            # The packet says this cannot be claimed here. Proposing it
            # anyway is the blocked-claim leak the suite counts.
            continue
        if effect_direction(proposition) != "harms_subject":
            # Only a mechanism that hurts whoever has it explains the
            # loss of the side it is stated against. An ambiguous one
            # is a diagnosis wearing a comparison's clothes.
            continue
        if contrast.subject is None:  # pragma: no cover - support kinds carry one
            continue
        hypothesis_id = f"floor-contrast-{position:03d}"
        proposals.append(
            HypothesisProposal(
                hypothesis_id=hypothesis_id,
                hypothesis_statement=_statement_for_contrast(contrast, proposition),
                proposition_type=proposition,
                proposed_subject=contrast.subject,
                supports=(
                    EvidenceRef(ref=f"contrast:{contrast.kind}:{position}", kind="observation"),
                ),
            )
        )
        bearings[hypothesis_id] = CONTRAST

    return EpisodeFloorAnswer(tuple(proposals), bearings)
