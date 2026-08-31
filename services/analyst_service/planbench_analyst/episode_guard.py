"""The rules an episode answer needs and a run-scope one does not.

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

**Rule 11 — a mechanism the detectors look for and did not find.** Five
proposition types name something a detector decides, and the detector
already applied its threshold; absence is read, not re-derived.

**Rule 12 — a component this episode records nothing about.** The
subject taxonomy is wider than any packet, and a claim may only blame
what the comparison declared or what something measured.

**Rule 13 — both sides weighed where nothing reached ``support``.**
Rule 11 withdraws one proposition type; the claim came back under
another. This asks the packet rather than the type, and drops rather
than demotes, because the comparison is in the sentence.

A third rule for the same family lives in the packet rather than here:
``EpisodePacket.blocked_claim_types`` refuses
``component_specific_attribution`` outright when no contrast reached
``support`` strength. It belongs there because the model is told before
it drafts — a refusal at this layer costs a round and returns silence,
and silence is the failure this scope is being measured on.

The annotations these rules read and write travel beside the response,
never inside it: ``HypothesisProposal`` forbids extra fields, and adding
one would bump the explanation schema and rebuild every fixture to
record something only this scope asks about.
"""

from __future__ import annotations

import re
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


#: A stand-in for the losing side's label, so one pattern per winning
#: phrase serves every episode rather than being rebuilt per round.
_LOSER = "\x00loser\x00"

#: How many words may sit between the label and the claim.
#:
#: **Because none was allowed, and an adverb was enough to walk past
#: the rule.** The check was ``f"{label} {word}" in sentence``, which
#: catches "C5 wins" and misses "C5 clearly wins", "C5 ultimately won"
#: and "C5 is clearly faster" — on the one hard constraint whose
#: ceiling is zero, and whose whole job is to stop the analyst handing
#: the episode to the side the platform did not name.
#:
#: Three, measured rather than guessed: run over every statement that
#: survived on all four recorded arms, a gap of zero, one, two and
#: three each flag exactly nothing. The widening is free on the data in
#: hand, so it is taken at the widest value that was tested.
_ADVERB_GAP = 3


def _victory_pattern(phrase: str) -> re.Pattern[str]:
    """The label, then the phrase, with room for an adverb at each join.

    The gap has to be allowed *inside* a phrase as well as before it.
    "is faster" is two words, and "is clearly faster" puts the adverb
    between them — which is where English puts it.
    """
    gap = rf"(?:\W+\w+){{0,{_ADVERB_GAP}}}\W+"
    return re.compile(
        re.escape(_LOSER) + "".join(gap + re.escape(word) for word in phrase.split()) + r"(?!\w)"
    )


_CLAIMS_VICTORY: dict[str, re.Pattern[str]] = {
    phrase: _victory_pattern(phrase) for phrase in _WINNING_WORDS
}


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
        if _CLAIMS_VICTORY[word].search(sentence.replace(loser_label.lower(), _LOSER)):
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
    # **The contrast doing the supporting has to be about the component
    # being blamed.** The term used to be granted on an empty set —
    # rule 6 refuses a citation naming a *different* component, so
    # silence was read as silence rather than as a match. That holds
    # while every supporting contrast carries a subject, and stopped
    # holding when one arrived without: a `near_miss_cluster` contrast
    # has no mechanism behind it and therefore no owner, so a claim
    # citing it named whichever component it liked and collected
    # `subject_match` for having cited nothing that could disagree.
    #
    # Read off the *supporting* contrasts rather than off everything
    # cited. An observation is about a candidate, not a component, and
    # requiring the whole citation list to agree would refuse the
    # ordinary shape of a finding: one contrast that carries the
    # mechanism, one `obs:` that shows it happened here.
    #
    # Measured before it was written: on the last sweep exactly one
    # statement loses the term, and it is one a scorer marked `wrong` —
    # "local_controller refused to traverse a passage of width …",
    # resting on a contrast with no subject at all. No statement marked
    # `explains` is touched.
    supporting_subjects = {
        fact.subject
        for ref in supporting
        if (fact := view.fact(ref)) is not None and fact.subject is not None
    }
    if supporting:
        matched = proposal.proposed_subject in supporting_subjects
    else:
        matched = not subjects or proposal.proposed_subject in subjects
    if matched:
        met.append("subject_match")

    # **Polarity is the registry's word about the mechanism the packet
    # put behind this contrast**, not only about the type the model
    # chose. A supporting contrast that names a different mechanism is
    # not evidence that this one harms the side it is stated against.
    if effect_direction(proposal.proposition_type) == "harms_subject" and (
        not supporting or matched
    ):
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


#: The components a candidate declares, which are in scope on every
#: episode by virtue of being the thing compared.
DECLARED_COMPONENT_FIELDS: tuple[str, ...] = (
    "global_planner",
    "local_controller",
    "local_controller_config",
)


def _subject_absent_from_episode(proposal: HypothesisProposal, view: EpisodeView) -> str | None:
    """Rule 12. A component this episode records nothing about.

    The subject taxonomy is wider than any one episode. Eight subjects
    may be named; a comparison declares three components per side, and
    the rest — ``costmap_inflation``, ``task_geometry``, the providers —
    enter a packet only when something measured them: an inflation
    margin, a passage width. When nothing did, the packet holds no fact
    about that subject, and a sentence blaming it blames a part of the
    stack this episode did not observe.

    A hand-scored arm produced exactly that: *"costmap_inflation refused
    to maintain clearance above the minimum threshold 0.15"*, on a
    packet with no robot block, no inflation margin and no threshold
    anywhere — only ``min_clearance = 0.148568``, from which 0.15 was
    rounded into a limit nobody set. The previous rubric read it as
    plausible with every reference opening, because each ref did open.
    What none of them was about was costmap inflation.

    **The declared components stay in scope regardless of which facts
    carry a subject.** ``obs:`` and ``diag:`` facts record none, so
    demanding a subject-bearing fact for every proposal refuses ordinary
    findings about the local controller — it did, on thirteen of
    twenty-five proposals, before this was narrowed to the subjects a
    packet has to earn.
    """
    declared = {
        field
        for candidate in view.packet.candidates
        for field in DECLARED_COMPONENT_FIELDS
        if getattr(candidate, field, None)
    }
    subject = proposal.proposed_subject
    if subject in declared or view.refs_for_subject(subject):
        return None
    return f"this episode records nothing about {subject}"


def _compares_without_support(proposal: HypothesisProposal, view: EpisodeView) -> str | None:
    """Rule 13. Both sides weighed on a packet that can carry nothing.

    Rule 11 withdraws ``component_specific_attribution`` when no contrast
    reached ``support``. The claim moved: the deployment arm made the
    same comparison under ``local_minimum_entrapment``, subject
    ``global_planner``, citing ``component_differs`` — "global_planner of
    C5 triggered a replan during the stuck cluster while C1 did not".
    Both statements a scorer marked `wrong` on that arm are that shape,
    and neither came from a rewrite. Blocking one proposition type
    blocked a label, not a move.

    So the condition is the packet's, not the type's: where nothing
    reached ``support``, a sentence weighing the two sides against each
    other has nothing under it whatever it is called.

    **Dropped rather than demoted.** Rule 10 keeps an over-claimed
    proposal as a diagnosis, which is right when the register was the
    only thing wrong — an observation about one side stays true when it
    stops claiming to explain the verdict. It is not right here: the
    comparison is in the sentence, so demoting relabels a claim the
    reader still meets in full.

    **Why it is not simply "unmet contract plus a comparison".** That was
    the first draft, and measuring it first is the reason it is not the
    code: on the deployment arm it removed five of the six episodes a
    scorer marked `explains`. Explaining why one side beat the other
    *is* comparing them, and most such statements miss a contract term
    while being exactly what this scope exists to produce. Restricted to
    packets with no supported contrast, the same measurement catches the
    two wrong statements and touches no `explains` on any of the three
    recorded arms.

    Read against labels, like rule 9: a candidate id never reaches the
    model, so a sentence can only name the two sides by their labels.
    """
    if any(
        fact.ref.startswith("contrast:") and str(fact.value) == "support" for fact in view.facts
    ):
        return None
    verdict = view.packet.verdict
    labels = {
        view.aliases.label_for(str(verdict.candidate_a)),
        view.aliases.label_for(str(verdict.candidate_b)),
    }
    sentence = proposal.hypothesis_statement
    named = {label for label in labels if re.search(rf"\b{re.escape(label)}\b", sentence)}
    if len(named) < 2:
        return None
    return (
        f"the statement weighs {sorted(named)} against each other and no contrast in this "
        "packet reached support strength"
    )


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

        # **Blamed a part of the stack this episode did not observe.**
        # Checked here, after the detector rule, because both are about
        # whether the thing named was seen at all and neither depends on
        # the register the proposal was offered in.
        absent = _subject_absent_from_episode(proposal, view)
        if absent is not None:
            blocked.append(Blocked(proposal.hypothesis_id, "subject_absent_from_episode", absent))
            continue

        # **Weighed both sides on a packet with nothing at support
        # strength.** Beside rules 11 and 12 because all three ask
        # whether there was anything to say, not which register it was
        # said in — and this one has to run before the register branch
        # below, which would otherwise keep it as a diagnosis.
        unbacked = _compares_without_support(proposal, view)
        if unbacked is not None:
            blocked.append(Blocked(proposal.hypothesis_id, "compares_without_support", unbacked))
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
