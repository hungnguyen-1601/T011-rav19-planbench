"""The promotion matrix: the only thing in the system that makes a claim.

Every rule here is deterministic and every refusal is recorded with a
reason. That combination is the point: an explanation panel that shows
nothing must be able to say *why* it shows nothing, or a reader will
assume the layer simply had no opinion when in fact a check refuted the
hypothesis.

**What the matrix reads.** The proposal (what is being asserted, about
which component, on what evidence), the record (how the orchestrator
adjudicated it, with which signed checker results), the tool catalog
(what each tool is licensed to establish) and the packet's known
unknowns. It never reads prose, a model's confidence, or a tool's
free-text purpose.

**The ceilings compose, they do not vote.** A claim may not exceed the
weakest of: the tool card's ``maximum_claim_level``, the ceiling implied
by the checker's input provenance, the ceiling implied by **every piece
of evidence the claim cites**, and the ceiling on the subject being
blamed. Four independent caps, minimum taken in one place. Provenance
appears twice in that list because it enters twice — a check run on
recorded inputs beside an observation somebody reconstructed is still
resting on reconstructed data.

**Refuting evidence wins.** One completed check that refutes the
proposition kills the claim, regardless of how many other checks
supported it. Rows in the ledger are not tallied — the layer is a filter
that discards, not a scorer that averages.

**Where the four levels come from**

``observed``
    a measurement over recorded data. No hypothesis needed, no analyst
    involved — see :func:`promote_measurement`.
``associated``
    a hypothesis backed by at least one behavioural pattern
    (observation, contrast or trace window), with no applicable
    mechanism check or none that concluded. This is the honest resting
    place of an idea the catalog cannot check, and it is where the
    hypothesis stays.
``mechanism_verified``
    a mechanism check completed, supported the proposition, ran on
    inputs its card accepts, and its card permits that level — **and**
    the mechanism is linked to the outcome by an execution observation
    plus an impact artifact. A checker verifies a narrow condition
    ("the planner returns no_path through this gap on this costmap");
    that the condition explains the result is a second statement, and
    without the link the claim is true, unconnected, and read as
    connected. No observation caps at ``observed`` (a measurement with
    no behaviour to be consistent with); no impact artifact caps at
    ``associated``.
``intervention_supported``
    a preregistered intervention in the research lane that tested *this*
    proposition on *this* subject and came out ``supported``. No tool
    card can grant this level; the evidence must be an
    :class:`~planbench_explanation.ledger.InterventionEvidence`, and a
    refuted or inconclusive one refuses the claim outright rather than
    falling back to a weaker rung.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_explanation.ledger import (
    Claim,
    EvidenceRef,
    HypothesisProposal,
    InvestigationRecord,
    KnownUnknown,
)
from planbench_explanation.levels import (
    ClaimLevel,
    PhrasePolicy,
    Qualifier,
    canonical_qualifiers,
    check_phrases,
    level_rank,
    weakest,
)
from planbench_explanation.propositions import PropositionType, require_assertable
from planbench_explanation.provenance import provenance_ceiling
from planbench_explanation.subjects import Subject, subject_ceiling
from planbench_explanation.tools import ToolCatalog, ToolNotInCatalog
from planbench_explanation.versioning import PROMOTION_MATRIX_VERSION

#: Evidence kinds that count as a behavioural pattern. A hypothesis
#: supported only by static facts has nothing to be "consistent with".
_PATTERN_KINDS = frozenset({"observation", "contrast", "trace_window"})


class PromotionOutcome(BaseModel):
    """A claim, or a refusal, and always the reasoning behind it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: Claim | None
    reasons: tuple[str, ...]

    @property
    def promoted(self) -> bool:
        return self.claim is not None


def _refuse(*reasons: str) -> PromotionOutcome:
    return PromotionOutcome(claim=None, reasons=tuple(reasons))


def promote(
    *,
    claim_id: str,
    proposal: HypothesisProposal,
    record: InvestigationRecord,
    catalog: ToolCatalog,
    statement: str,
    scope: str,
    known_unknowns: Sequence[KnownUnknown] = (),
    h4_accounting_complete: bool = False,
    phrase_policy: PhrasePolicy | None = None,
) -> PromotionOutcome:
    """Adjudicate one proposal against its record. Deterministic.

    ``statement`` is the rendered sentence (E4 supplies it from a
    template). It is checked against the phrase whitelist for the level
    that was earned, here rather than only at render time: the wording
    and the level are decided together or they drift apart.
    """
    reasons: list[str] = []

    if not statement.strip():
        return _refuse("empty_statement")

    if record.proposal_ref != proposal.hypothesis_id:
        return _refuse(f"record_proposal_mismatch:{record.proposal_ref}!={proposal.hypothesis_id}")

    blockers = [
        unknown.id
        for unknown in known_unknowns
        if proposal.proposition_type in unknown.blocks_claim_types
    ]
    if blockers:
        return _refuse(*(f"blocked_by_known_unknown:{blocker}" for blocker in sorted(blockers)))

    if record.status != "checked":
        return _refuse(f"record_status:{record.status}")

    if not proposal.supports:
        return _refuse("no_supporting_evidence")
    if any(ref.provenance == "missing" for ref in proposal.supports):
        return _refuse("supporting_evidence_missing")

    # A claim is no stronger than the weakest thing it cites. The first
    # cut read provenance off the checker results only, and turned the
    # provenance of the *supporting evidence* into a qualifier — so an
    # execution observation rebuilt after the fact, cited beside a
    # checker that ran on recorded inputs, produced a
    # ``mechanism_verified`` claim wearing a ``reconstructed_input``
    # badge. The badge is not a ceiling. Every cited support caps, and
    # deliberately every one of them rather than some subset judged to
    # be "the linking evidence": deciding which citation is load-bearing
    # is exactly the judgement this layer refuses to make on the
    # reader's behalf.
    ceiling = weakest(
        subject_ceiling(proposal.proposed_subject, h4_accounting_complete=h4_accounting_complete),
        *(provenance_ceiling(ref.provenance) for ref in proposal.supports),
    )

    checked_level: ClaimLevel | None = None
    reconstructed_inputs = any(ref.provenance == "reconstructed" for ref in proposal.supports)

    for result in record.checker_results:
        label = f"{result.tool_id}@{result.tool_version}"
        try:
            card = catalog.card(result.tool_id, result.tool_version)
        except ToolNotInCatalog:
            return _refuse(f"unknown_tool:{label}")

        if proposal.proposition_type in card.proposition_policy.forbidden_inference_types:
            return _refuse(f"forbidden_inference:{label}:{proposal.proposition_type}")

        if result.execution_status != "completed":
            reasons.append(f"{label}:execution_status={result.execution_status}")
            continue

        verdict = result.verdict_for(proposal.proposition_type)
        if verdict is None:
            reasons.append(f"{label}:silent_on:{proposal.proposition_type}")
            continue
        if verdict == "refuted":
            return _refuse(f"refuted_by:{label}")
        if verdict == "inconclusive":
            reasons.append(f"{label}:inconclusive")
            continue

        if proposal.proposition_type not in card.proposition_policy.supported_proposition_types:
            reasons.append(f"{label}:result_exceeds_card:{proposal.proposition_type}")
            continue
        if result.input_provenance not in card.evidence_policy.allowed_input_provenance:
            reasons.append(f"{label}:provenance_not_accepted:{result.input_provenance}")
            continue

        if result.input_provenance == "reconstructed":
            reconstructed_inputs = True

        contribution = weakest(
            card.proposition_policy.maximum_claim_level,
            provenance_ceiling(result.input_provenance),
        )
        reasons.append(f"{label}:supported:{contribution}")
        if checked_level is None or level_rank(contribution) > level_rank(checked_level):
            checked_level = contribution

    has_execution_observation = any(ref.kind in _PATTERN_KINDS for ref in proposal.supports)

    if record.intervention is not None:
        intervention = record.intervention
        if intervention.proposition_type != proposal.proposition_type:
            return _refuse(
                f"intervention_tests_another_proposition:{intervention.proposition_type}"
            )
        if intervention.subject != proposal.proposed_subject:
            return _refuse(f"intervention_acts_on_another_subject:{intervention.subject}")
        if intervention.verdict == "refuted":
            return _refuse(f"refuted_by_intervention:{intervention.preregistration_ref}")
        if intervention.verdict != "supported":
            return _refuse(f"intervention_inconclusive:{intervention.preregistration_ref}")
        if intervention.scope != scope:
            return _refuse(f"scope_mismatch:{scope!r}!={intervention.scope!r}")
        level = weakest("intervention_supported", ceiling)
        reasons.append(
            f"intervention:{intervention.preregistration_ref}:{intervention.effect_direction}"
        )
    elif checked_level is not None:
        level = weakest(checked_level, ceiling)
    else:
        if not has_execution_observation:
            return _refuse("no_pattern_evidence", *reasons)
        level = weakest("associated", ceiling)
        reasons.append("no_applicable_check:resting_at_associated")

    # A verified mechanism is a verified *narrow condition* — "the planner
    # returns no_path through this gap on this costmap". Saying it explains
    # the outcome needs two more things the checker cannot supply: an
    # observation that the condition was hit during execution, and an
    # impact artifact tying it to the objective decomposition. Without
    # them the claim is true and unconnected, which reads to a human as
    # connected. So the link is a requirement of the level, not advice in
    # a docstring.
    # The two halves cap at different rungs, because they are missing
    # different things. With no execution observation there is no
    # behaviour for the mechanism to be "consistent with" — what remains
    # is a measurement, so ``observed``. With an observation but no
    # impact artifact the pattern is real and its share of the utility
    # gap is unquantified, which is exactly ``associated``.
    if level_rank(level) >= level_rank("mechanism_verified"):
        if not has_execution_observation:
            level = weakest(level, "observed")
            reasons.append("mechanism_not_linked_to_outcome:no_execution_observation")
        if record.impact_ref is None:
            level = weakest(level, "associated")
            reasons.append("mechanism_not_linked_to_outcome:no_impact_ref")

    qualifiers: set[Qualifier] = set()
    if record.evidence_lane == "research":
        qualifiers.add("research_lane")
    if reconstructed_inputs:
        qualifiers.add("reconstructed_input")
    if record.impact_ref is not None:
        if record.impact_ref.impact_kind == "attributable_effect_estimate":
            qualifiers.add("estimated")
        if record.impact_ref.profile_weighted:
            qualifiers.add("profile_weighted")

    violations = check_phrases(
        statement, level, **({"policy": phrase_policy} if phrase_policy else {})
    )
    if violations:
        return _refuse(
            *(f"forbidden_phrase_at_{level}:{phrase}" for phrase in violations), *reasons
        )

    claim = Claim(
        claim_id=claim_id,
        level=level,
        proposition_type=proposal.proposition_type,
        subject=proposal.proposed_subject,
        statement=statement,
        scope=scope,
        supports=proposal.supports,
        record_ref=record.record_id,
        qualifiers=canonical_qualifiers(qualifiers),
        impact_ref=record.impact_ref,
        promotion_matrix_version=PROMOTION_MATRIX_VERSION,
    )
    return PromotionOutcome(claim=claim, reasons=tuple(reasons))


def promote_measurement(
    *,
    claim_id: str,
    proposition_type: PropositionType,
    subject: Subject,
    statement: str,
    scope: str,
    supports: Sequence[EvidenceRef],
    record_ref: str,
    phrase_policy: PhrasePolicy | None = None,
) -> PromotionOutcome:
    """An ``observed`` claim: something the platform measured.

    No hypothesis and no analyst are involved — this is the route the
    waterfall's own numbers take onto the panel. It stays inside the
    matrix rather than bypassing it so that measurements are subject to
    the same wording rule as everything else: a paired mean is a
    measurement, and a sentence about it may not say "because".
    """
    require_assertable(proposition_type, field="proposition_type")
    if not supports:
        return _refuse("no_supporting_evidence")
    if any(ref.provenance != "recorded" for ref in supports):
        return _refuse("measurement_requires_recorded_evidence")

    violations = check_phrases(
        statement, "observed", **({"policy": phrase_policy} if phrase_policy else {})
    )
    if violations:
        return _refuse(*(f"forbidden_phrase_at_observed:{phrase}" for phrase in violations))

    claim = Claim(
        claim_id=claim_id,
        level="observed",
        proposition_type=proposition_type,
        subject=subject,
        statement=statement,
        scope=scope,
        supports=tuple(supports),
        record_ref=record_ref,
        promotion_matrix_version=PROMOTION_MATRIX_VERSION,
    )
    return PromotionOutcome(claim=claim, reasons=("measurement",))
