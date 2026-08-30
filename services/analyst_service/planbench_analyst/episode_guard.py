"""Two more rules, for the two ways an episode answer can go wrong.

The eight rules in :mod:`planbench_analyst.guard` run over an episode
round unchanged — they ask about refs, quantities, blocked types, tool
cards, wording and subjects, and none of that changes with scope. What
changes is that this scope has an answer the platform already computed,
and a second register a proposal can be offered in.

**Rule 9 — a statement may not contradict the verdict.** Who won is
arithmetic over two rows the scoring pass stored. A sentence saying the
other side won is not a hypothesis about a mechanism; it is a different
answer to a question that was not asked of the model.

**Rule 10 — a contrast has to earn the word.** Being offered as bearing
on the verdict takes four things, and the one that carries the weight is
occurrence: evidence that the mechanism happened **in this episode**. A
curated entry saying the mechanism exists and behaves a certain way is a
reference, not an occurrence, and a finding resting on one has said
nothing about this episode at all. Unmet, the proposal is **kept and
demoted** to a diagnosis rather than dropped — the observation is
usually real and only the register was wrong.

The annotations these rules read and write travel beside the response,
never inside it: ``HypothesisProposal`` forbids extra fields, and adding
one would bump the explanation schema and rebuild every fixture to
record something only this scope asks about.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planbench_analyst.analyst import RoundCost
from planbench_analyst.episode_view import EpisodeView
from planbench_analyst.guard import Blocked, guard
from planbench_explanation.integration import DETECTION_HYPOTHESES
from planbench_explanation.ledger import HypothesisProposal
from planbench_explanation.propositions import effect_direction
from planbench_explanation.protocol import AnalysisResponse
from planbench_explanation.tools import ToolCatalog

DIAGNOSIS = "diagnosis"
CONTRAST = "contrast"

#: The four things a contrast has to have, in the order they are checked.
#: ``mechanism_reference`` is deliberately absent: it is recorded when
#: present and never required.
CONTRACT_TERMS: tuple[str, ...] = (
    "contrast_support",
    "occurrence_evidence",
    "subject_match",
    "polarity_match",
)

#: Ref prefixes that show a mechanism **happened here**.
OCCURRENCE_PREFIXES: tuple[str, ...] = ("obs:", "diag:", "attempts:", "checker:")

#: Ref prefixes that describe a mechanism in general.
REFERENCE_PREFIXES: tuple[str, ...] = ("kb:", "trait:")

#: Words that assert an outcome. Read against the labels in play, so
#: "C2 wins" is caught and "C2 stalls" is not.
_WINNING_WORDS: tuple[str, ...] = (
    "wins",
    "won",
    "beats",
    "outperforms",
    "is better",
    "is faster",
    "is safer",
    "did better",
    "came out ahead",
)


@dataclass(frozen=True)
class EpisodeAnnotation:
    """What register a proposal was offered in, and what it satisfied."""

    bearing: str = DIAGNOSIS
    contract: tuple[str, ...] = ()
    occurrence_evidence_refs: tuple[str, ...] = ()
    mechanism_reference_refs: tuple[str, ...] = ()
    supersedes: str | None = None


@dataclass(frozen=True)
class EpisodeRoundResult:
    """The response, and the annotations that belong beside it.

    Two objects rather than one wider one. The response is the wire
    contract an external analyst answers on; annotations are this
    scope's own bookkeeping, and a round that lost them would not know
    which of its proposals claimed to explain the verdict.
    """

    response: AnalysisResponse
    annotations: dict[str, EpisodeAnnotation] = field(default_factory=dict)
    blocked: tuple[Blocked, ...] = ()
    #: What the round spent. Carried here rather than left to the
    #: caller to find, because a spend cap reading zero for every
    #: round is a cap on nothing — the same failure as a latency term
    #: nobody measured, which turns a slow arm into a fast one.
    cost: RoundCost = field(default_factory=lambda: RoundCost())
    ranking: tuple[str, ...] = ()
    flags: tuple[tuple[str, str], ...] = ()

    def of(self, bearing: str) -> tuple[HypothesisProposal, ...]:
        return tuple(
            proposal
            for proposal in self.response.proposals
            if self.annotations.get(proposal.hypothesis_id, EpisodeAnnotation()).bearing == bearing
        )


def contradicts_verdict(proposal: HypothesisProposal, view: EpisodeView) -> str | None:
    """Rule 9. A sentence that hands the episode to the other side.

    Read against labels, since the model never sees a real candidate id:
    the winner's label may be said to have won and the loser's may not.
    A verdict with no direction lets both through — there is nothing to
    contradict, and the contrast rules have already withheld everything
    that needed a losing side.
    """
    verdict = view.packet.verdict
    if not verdict.has_direction:
        return None
    loser_label = view.aliases.label_for(str(verdict.loser))
    sentence = proposal.hypothesis_statement.lower()
    for word in _WINNING_WORDS:
        marker = f"{loser_label.lower()} {word}"
        if marker in sentence:
            return f"the statement says {loser_label} {word}, and this episode went the other way"
    return None


def contract_terms_met(
    proposal: HypothesisProposal,
    view: EpisodeView,
) -> tuple[tuple[str, ...], EpisodeAnnotation]:
    """Rule 10. Which of the four a contrast satisfies, and what it cited.

    Every term is decided from the packet's own index — the strength of
    the contrast it cites, the prefix of each ref, the subject the fact
    records, the polarity the mechanism registry declares. None of it is
    read out of the sentence, because a sentence is what the model
    writes and every one of these is something the platform knows.
    """
    cited = proposal.supports + proposal.contradicts
    occurrence = tuple(ref.ref for ref in cited if ref.ref.startswith(OCCURRENCE_PREFIXES))
    references = tuple(ref.ref for ref in cited if ref.ref.startswith(REFERENCE_PREFIXES))

    supporting = []
    for ref in cited:
        if not ref.ref.startswith("contrast:"):
            continue
        fact = view.fact(ref.ref)
        if fact is not None and fact.value == "support":
            supporting.append(ref.ref)

    met: list[str] = []
    if supporting:
        met.append("contrast_support")
    if occurrence:
        met.append("occurrence_evidence")

    subjects = {
        fact.subject
        for ref in cited
        if (fact := view.fact(ref.ref)) is not None and fact.subject is not None
    }
    if not subjects or proposal.proposed_subject in subjects:
        # No cited fact attributes anything: rule 6 already refuses a
        # citation that names a *different* component, so silence here
        # is silence and not a match against something.
        met.append("subject_match")

    if effect_direction(proposal.proposition_type) == "harms_subject":
        met.append("polarity_match")

    annotation = EpisodeAnnotation(
        bearing=CONTRAST,
        contract=tuple(met),
        occurrence_evidence_refs=occurrence,
        mechanism_reference_refs=references,
    )
    missing = tuple(term for term in CONTRACT_TERMS if term not in met)
    return missing, annotation


#: Which detector answers for a proposition type, reversed from the
#: platform's own mapping rather than restated.
#:
#: ``DETECTION_HYPOTHESES`` says what a detection may be proposed as;
#: read the other way it says which detector would have seen this
#: mechanism if it were there. Derived rather than written out, so a
#: sixth detector added upstream arrives here without anybody
#: remembering to copy it.
DETECTORS_FOR: dict[str, frozenset[str]] = {}
for _detector, (_type, _subject, _tool) in DETECTION_HYPOTHESES.items():
    DETECTORS_FOR[_type] = DETECTORS_FOR.get(_type, frozenset()) | {_detector}


def _detector_silent(proposal: HypothesisProposal, view: EpisodeView) -> str | None:
    """Why this mechanism could not have been seen, or ``None``.

    Citing an observation of that detector is the way past: if the thing
    fired somewhere this proposal points at, the claim is about
    something that happened, whatever else may be wrong with it.
    """
    wanted = DETECTORS_FOR.get(proposal.proposition_type, frozenset())
    if not wanted:
        # Only five types map to a detector, and this must not become a
        # requirement that every mechanism have one — that would refuse
        # every hypothesis the detectors were never built to see.
        return None
    fired = {
        fact.ref.split(":")[1]
        for fact in view.facts
        if fact.ref.startswith("obs:") and "/" not in fact.ref
    }
    cited = {
        ref.ref.split(":")[1]
        for ref in proposal.supports + proposal.contradicts
        if ref.ref.startswith("obs:")
    }
    if wanted & fired or wanted & cited:
        return None
    return f"{sorted(wanted)} did not fire in this episode"


def episode_guard(
    response: AnalysisResponse,
    view: EpisodeView,
    *,
    catalog: ToolCatalog,
    bearings: dict[str, str] | None = None,
    critic: bool = True,
) -> EpisodeRoundResult:
    """The eight rules, then the two this scope adds.

    Order matters: rules 1–8 drop what may not be submitted at all, and
    only what survives is asked which register it belongs in. Running
    rule 10 first would demote proposals that were about to be refused
    outright, and the count of demotions is a measurement.
    """
    declared = dict(bearings or {})
    base = guard(response, view, catalog=catalog, critic=critic)  # type: ignore[arg-type]
    if base.response.abstained:
        return EpisodeRoundResult(
            response=base.response,
            blocked=base.blocked,
            ranking=base.ranking,
            flags=base.flags,
        )

    kept: list[HypothesisProposal] = []
    blocked = list(base.blocked)
    annotations: dict[str, EpisodeAnnotation] = {}

    for proposal in base.response.proposals:
        # **A mechanism the detectors look for and did not find.**
        #
        # Five proposition types name something a detector decides:
        # `replan_instability` is what `replan_storm` reports, and that
        # detector fires at three replans in a window, not one. Across a
        # scored hold-out the model called a single replan instability
        # five times and a person marked all five wrong; the rule also
        # catches the other arm's one wrong statement, and in neither
        # arm does it touch anything scored `holds`.
        #
        # The threshold is deliberately not repeated. The detector
        # applied it already, so "did it fire" is the platform's own
        # answer to a question this layer would otherwise re-derive and
        # then drift from. What is read is absence, not arithmetic.
        #
        # **Here rather than in the shared guard**, which is where it
        # was first put and where it broke two run-scope tests by
        # firing ahead of rule 6. The evidence for it is entirely from
        # episode packets; a rule that has only been measured at one
        # scope belongs at that scope until somebody measures the other.
        silent = _detector_silent(proposal, view)
        if silent is not None:
            blocked.append(Blocked(proposal.hypothesis_id, "mechanism_detector_silent", silent))
            continue

        contradiction = contradicts_verdict(proposal, view)
        if contradiction is not None:
            blocked.append(Blocked(proposal.hypothesis_id, "contradicts_verdict", contradiction))
            continue

        wanted = declared.get(proposal.hypothesis_id, DIAGNOSIS)
        if wanted != CONTRAST:
            annotations[proposal.hypothesis_id] = EpisodeAnnotation(bearing=DIAGNOSIS)
            kept.append(proposal)
            continue

        missing, annotation = contract_terms_met(proposal, view)
        if missing:
            # Demoted, not dropped: the observation is usually real and
            # only the register was wrong. Recorded as a block anyway,
            # because how often a model over-claims the register is a
            # number worth having.
            blocked.append(
                Blocked(
                    proposal.hypothesis_id,
                    "contrast_contract_unmet",
                    f"missing {list(missing)}",
                )
            )
            annotations[proposal.hypothesis_id] = EpisodeAnnotation(
                bearing=DIAGNOSIS,
                contract=annotation.contract,
                occurrence_evidence_refs=annotation.occurrence_evidence_refs,
                mechanism_reference_refs=annotation.mechanism_reference_refs,
            )
        else:
            annotations[proposal.hypothesis_id] = annotation
        kept.append(proposal)

    if not kept:
        reasons = sorted({item.rule for item in blocked})
        return EpisodeRoundResult(
            response=AnalysisResponse(
                analysis_run_id=response.analysis_run_id,
                analyst_bundle_id=response.analyst_bundle_id,
                abstained=True,
                abstention_reason=(
                    "every proposal was refused before submission ("
                    + ", ".join(reasons)
                    + "); an abstention with a reason beats a claim the platform would refuse"
                ),
            ),
            blocked=tuple(blocked),
        )

    return EpisodeRoundResult(
        response=AnalysisResponse(
            analysis_run_id=response.analysis_run_id,
            analyst_bundle_id=response.analyst_bundle_id,
            proposals=tuple(kept),
        ),
        annotations=annotations,
        blocked=tuple(blocked),
        ranking=base.ranking,
        flags=base.flags,
    )


def carry_annotation(
    annotations: dict[str, EpisodeAnnotation],
    *,
    old_id: str,
    new_id: str,
) -> dict[str, EpisodeAnnotation]:
    """Move an annotation onto the id a revision produced.

    A revised proposal is a new content hash and therefore a new id. The
    annotation has to follow, carrying the id it came from: without it a
    revision silently becomes a diagnosis, which is the register a
    proposal falls back to.
    """
    moved = dict(annotations)
    previous = moved.pop(old_id, EpisodeAnnotation())
    moved[new_id] = EpisodeAnnotation(
        bearing=previous.bearing,
        contract=previous.contract,
        occurrence_evidence_refs=previous.occurrence_evidence_refs,
        mechanism_reference_refs=previous.mechanism_reference_refs,
        supersedes=old_id,
    )
    return moved
