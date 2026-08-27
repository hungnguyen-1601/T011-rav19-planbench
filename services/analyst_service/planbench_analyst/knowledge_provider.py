"""Retrieval, and the two things it is structurally unable to do.

An analyst that only reads one packet can only propose what that packet
suggests. The knowledge base exists so it can also consider mechanisms
somebody wrote down once — and the danger of that is obvious enough that
the contract was built before any retrieval was: a retriever that could
hand back the mechanism text, its sources and its review status would be
a retriever whose confidence decides what gets claimed.

So this provider returns **keys**.
:class:`~planbench_explanation.knowledge_contract.MechanismReferenceCandidate`
has no field for the mechanism, the sources or the review status, and
``extra="forbid"`` turns an attempt to add one into an error at the
boundary. The platform resolves the keys against its own copy, and
``resolve_candidates`` is where "may this back a claim" is answered.

**Lexical, deliberately.** Five entries and six trait rows do not need
an embedding index; they need a match on the detection type, the subject
and the component names, which is what the activation conditions are
already written in. A vector index here would be a second thing to keep
in step with the KB for no measurable gain — and A6 is where a gain
would have to be measured before it is worth having.

**``retrieval_score`` is not confidence.** It orders one round's offers
and nothing reads it afterwards. A confident retrieval of the wrong
entry is precisely the failure the separation exists for, so the score
never leaves this module except as a debugging field on the candidate.

**Traits are offered the same way.** M3 gave algorithm natures a table;
an analyst may cite one as ``trait:<algorithm_id>#weakness:<i>``, and an
unapproved row may widen the hypothesis space and may not promote a
claim — the same rule the knowledge base runs under, applied to the same
kind of sentence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from planbench_benchmark.traits_store import TraitSource
from planbench_explanation.case_packet import CasePacket
from planbench_explanation.knowledge import (
    KNOWLEDGE_BASE,
    KNOWLEDGE_BASE_ID,
    KNOWLEDGE_BASE_VERSION,
    KnowledgeEntry,
)
from planbench_explanation.knowledge_contract import (
    KnowledgeQuery,
    KnowledgeResult,
    MechanismReferenceCandidate,
)

__all__ = [
    "RETRIEVAL_VERSION",
    "TraitOffer",
    "query_for",
    "retrieve",
    "trait_offers",
]

#: Bumped when the matching below changes. Part of what a bundle pins:
#: two analysts offered different entries for one packet are two
#: systems, however identical their prompts.
RETRIEVAL_VERSION = "lexical-1.0.0"

#: How many keys one round may be offered. A retriever that answers with
#: the whole base has not retrieved anything, and every extra key is
#: prompt budget spent on a mechanism nobody asked about.
MAX_OFFERS = 5


def query_for(packet: CasePacket, *, excluded: Sequence[str] = ()) -> KnowledgeQuery:
    """The case as features, never as prose.

    A provider handed the case narrative is a provider given room to
    answer the narrative rather than the evidence — so what travels is
    the detection types, the components and the task, which is the same
    vocabulary the activation conditions are written in.
    """
    components: list[str] = []
    for candidate in packet.candidates:
        components.extend(
            (
                candidate.global_planner,
                candidate.local_controller,
                candidate.local_controller_config,
            )
        )
    return KnowledgeQuery(
        task_features=(packet.task.task_profile_id,),
        candidate_components=tuple(dict.fromkeys(components)),
        observations=tuple(dict.fromkeys(item.type for item in packet.observations)),
        excluded_mechanisms=tuple(excluded),
    )


def _score(entry: KnowledgeEntry, query: KnowledgeQuery) -> float:
    """How well one entry's conditions line up with this case.

    Detection type is the anchor: an entry whose conditions name none of
    the detections in this packet is an entry about a different run,
    whatever else it matches. Subject and components only break ties.
    """
    if entry.proposition_type in query.excluded_mechanisms:
        return 0.0
    detections = set(entry.conditions.detection_types) & set(query.observations)
    if not detections:
        return 0.0
    score = 0.6 + 0.1 * min(len(detections), 2)
    if entry.conditions.subject in query.candidate_components:
        score += 0.1
    if any(entry.conditions.subject in item for item in query.candidate_components):
        score += 0.05
    return min(score, 1.0)


def retrieve(
    query: KnowledgeQuery,
    *,
    entries: Sequence[KnowledgeEntry] = KNOWLEDGE_BASE,
    limit: int = MAX_OFFERS,
) -> KnowledgeResult:
    """Offer keys, ranked, for the platform to resolve.

    Nothing here reads ``review_status`` — not because it does not
    matter but because it is not this side's answer. An unreviewed entry
    is offered exactly like an approved one, and
    ``resolve_candidates`` is where the difference is applied. Filtering
    here would move the promotion rule into retrieval, where nobody
    would be able to see it.
    """
    scored = [(score, entry) for entry in entries if (score := _score(entry, query)) > 0.0]
    scored.sort(key=lambda pair: (-pair[0], pair[1].entry_id))
    return KnowledgeResult(
        entries=tuple(
            MechanismReferenceCandidate(
                knowledge_base_id=KNOWLEDGE_BASE_ID,
                entry_id=entry.entry_id,
                entry_version=entry.entry_version,
                retrieved_for=query.hypothesis_id,
                retrieval_score=round(score, 3),
            )
            for score, entry in scored[:limit]
        ),
        kb_version=KNOWLEDGE_BASE_VERSION,
        retrieval_version=RETRIEVAL_VERSION,
    )


@dataclass(frozen=True)
class TraitOffer:
    """One algorithm nature an analyst may cite, and whether it may lean on it."""

    ref: str
    algorithm_id: str
    kind: str
    text: str
    anchor: str
    review_status: str

    @property
    def may_support_a_claim(self) -> bool:
        """Approved rows only — the knowledge base's rule, same sentence."""
        return self.review_status == "approved"


def trait_offers(packet: CasePacket, traits: TraitSource) -> tuple[TraitOffer, ...]:
    """The natures of the algorithms this packet actually ran.

    Only those: a table of every algorithm the platform knows would put
    six paragraphs about controllers nobody ran into a prompt somebody
    pays for.

    An algorithm with no row contributes **no offer at all** rather than
    an empty one. "Nobody described this" belongs in the packet's own
    account of its gaps, not in a citation an analyst could lean on.
    """
    offers: list[TraitOffer] = []
    seen: set[str] = set()
    for candidate in packet.candidates:
        for algorithm_id in (candidate.global_planner, candidate.local_controller):
            if algorithm_id in seen:
                continue
            seen.add(algorithm_id)
            entry = traits.get(algorithm_id)
            if entry is None:
                continue
            for index, text in enumerate(entry.strengths):
                offers.append(
                    TraitOffer(
                        ref=f"trait:{algorithm_id}#strength:{index}",
                        algorithm_id=algorithm_id,
                        kind=entry.kind,
                        text=text,
                        anchor=entry.anchor,
                        review_status=entry.review_status,
                    )
                )
            for index, text in enumerate(entry.weaknesses):
                offers.append(
                    TraitOffer(
                        ref=f"trait:{algorithm_id}#weakness:{index}",
                        algorithm_id=algorithm_id,
                        kind=entry.kind,
                        text=text,
                        anchor=entry.anchor,
                        review_status=entry.review_status,
                    )
                )
    return tuple(offers)
