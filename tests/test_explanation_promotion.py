"""E0 — the promotion matrix, one rule per test.

The matrix is the only producer of claims, so these tests are the
specification of what the platform is willing to say out loud. Each one
pins a single rule and, where a claim is refused, checks the reason:
"nothing to show" and "a check refuted this" must not look the same to
the reader of a ledger.
"""

from __future__ import annotations

import pytest

from planbench_explanation import (
    CheckerResult,
    EvidencePolicy,
    EvidenceRef,
    HypothesisProposal,
    ImpactRef,
    InterventionEvidence,
    InvestigationRecord,
    KnownUnknown,
    PropositionOutcome,
    PropositionPolicy,
    ToolCard,
    ToolCatalog,
    ToolPurpose,
    promote,
    promote_measurement,
)
from planbench_explanation.versioning import PROMOTION_MATRIX_VERSION

SCOPE = "deployment warehouse_crossing_v1"

#: What makes a completed checker result a signed one.
SIGNATURE = {
    "evidence_artifact_ref": "artifacts/explain/check.json",
    "evidence_checksum": "e" * 64,
    "implementation_ref": "git:7a7c195aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
}

GAP_CARD = ToolCard(
    tool_id="gap_vs_footprint",
    tool_version="1.0.0",
    title="Check geometric passage feasibility",
    tool_class="mechanism_check",
    purpose=ToolPurpose(
        verifies={"geometric_infeasibility": "Required clearance exceeds passage width."},
        does_not_verify={
            "complete_utility_attribution": "This mechanism produced the whole gap in utility."
        },
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("geometric_infeasibility",),
        forbidden_inference_types=("complete_utility_attribution",),
        maximum_claim_level="mechanism_verified",
    ),
    evidence_policy=EvidencePolicy(
        allowed_input_provenance=("recorded", "verified_reconstruction", "reconstructed")
    ),
)

#: Deterministic, and still only correlational — the card says so.
LATENCY_CARD = ToolCard(
    tool_id="latency_vs_expanded_nodes",
    tool_version="1.0.0",
    title="Correlate expansions with control latency",
    tool_class="mechanism_check",
    purpose=ToolPurpose(
        verifies={"expansion_latency_association": "Latency tracks the number of expanded nodes."},
        does_not_verify={
            "candidate_latency_attribution": "The candidate's own compute produced the latency."
        },
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("expansion_latency_association",),
        forbidden_inference_types=("candidate_latency_attribution",),
        maximum_claim_level="associated",
    ),
    evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
)

CATALOG = ToolCatalog(catalog_version="1.0.0", cards=(GAP_CARD, LATENCY_CARD))

GAP_FACT = EvidenceRef(ref="fact:gap_width_B7", kind="fact")
DETOUR = EvidenceRef(ref="obs:detour_B7", kind="observation")


def proposal(**overrides: object) -> HypothesisProposal:
    fields: dict[str, object] = {
        "hypothesis_id": "hyp-004",
        "hypothesis_statement": "B's inflation closes the B7 gap",
        "proposition_type": "geometric_infeasibility",
        "proposed_subject": "costmap_inflation",
        "supports": (GAP_FACT, DETOUR),
    }
    fields.update(overrides)
    return HypothesisProposal(**fields)  # type: ignore[arg-type]


def gap_result(
    *, verdict: str = "supported", provenance: str = "recorded", status: str = "completed"
) -> CheckerResult:
    if status != "completed":
        return CheckerResult(
            request_id="req-017",
            tool_id="gap_vs_footprint",
            tool_version="1.0.0",
            execution_status=status,  # type: ignore[arg-type]
            input_provenance="missing",
        )
    return CheckerResult(
        request_id="req-017",
        tool_id="gap_vs_footprint",
        tool_version="1.0.0",
        execution_status="completed",
        input_provenance=provenance,  # type: ignore[arg-type]
        proposition_verdict=verdict,  # type: ignore[arg-type]
        supported_propositions=(
            PropositionOutcome(
                proposition_id="geometric_infeasibility_at_B7",
                proposition_type="geometric_infeasibility",
                result=verdict,  # type: ignore[arg-type]
            ),
        ),
        measurements={"passage_width_m": 0.68, "required_clearance_m": 0.74},
        evidence_artifact_ref="artifacts/explain/gap_check.json",
        evidence_checksum="e" * 64,
        implementation_ref="git:7a7c195aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )


#: The artifact that ties a verified mechanism to the utility gap.
#: Without it a mechanism claim cannot exceed ``associated``.
IMPACT = ImpactRef(
    artifact_ref="artifacts/explain/impact_detour_excision.json",
    impact_kind="observed_contribution",
    objective="time_efficiency",
    method="paired_objective_decomposition",
)


def record(**overrides: object) -> InvestigationRecord:
    fields: dict[str, object] = {
        "record_id": "rec-1",
        "proposal_ref": "hyp-004",
        "status": "checked",
        "checker_results": (gap_result(),),
        "impact_ref": IMPACT,
    }
    fields.update(overrides)
    return InvestigationRecord(**fields)  # type: ignore[arg-type]


def intervention(**overrides: object) -> InterventionEvidence:
    """A preregistered dose-response run that moved the mechanism."""
    fields: dict[str, object] = {
        "preregistration_ref": "prereg-07",
        "axes": ("inflation_radius_m",),
        "artifact_ref": "artifacts/research/dose_response.json",
        "proposition_type": "geometric_infeasibility",
        "subject": "costmap_inflation",
        "verdict": "supported",
        "effect_direction": "removed",
        "statistical_result_ref": "artifacts/research/ddu_ci.json",
        "scope": SCOPE,
    }
    fields.update(overrides)
    return InterventionEvidence(**fields)  # type: ignore[arg-type]


def run(
    *,
    statement: str = "the B7 passage is narrower than B's required clearance (verified)",
    **overrides: object,
):
    kwargs: dict[str, object] = {
        "claim_id": "claim-1",
        "proposal": proposal(),
        "record": record(),
        "catalog": CATALOG,
        "statement": statement,
        "scope": SCOPE,
    }
    kwargs.update(overrides)
    return promote(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The four rungs
# --------------------------------------------------------------------------


def test_a_supported_mechanism_check_on_recorded_inputs_reaches_mechanism_verified() -> None:
    outcome = run()
    assert outcome.promoted
    assert outcome.claim is not None
    assert outcome.claim.level == "mechanism_verified"
    assert outcome.claim.promotion_matrix_version == PROMOTION_MATRIX_VERSION
    assert outcome.claim.qualifiers == ()


def test_reconstructed_inputs_cap_the_same_check_at_associated() -> None:
    outcome = run(
        record=record(checker_results=(gap_result(provenance="reconstructed"),)),
        statement="the B7 passage is consistent with a closed gap",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "associated"
    assert "reconstructed_input" in outcome.claim.qualifiers


def test_a_reconstructed_observation_caps_the_claim_even_on_recorded_checker_inputs() -> None:
    """Provenance enters twice, and both entrances are ceilings.

    Checker inputs recorded, impact artifact present, and the execution
    observation the claim leans on rebuilt after the fact. The first cut
    read provenance off the checker only and turned the observation's
    provenance into a badge — so this combination produced
    ``mechanism_verified`` with a ``reconstructed_input`` qualifier,
    which is a claim standing on rebuilt data while announcing the fact
    in a footnote.
    """
    rebuilt_observation = EvidenceRef(
        ref="obs:detour_B7", kind="observation", provenance="reconstructed"
    )
    outcome = run(
        proposal=proposal(supports=(GAP_FACT, rebuilt_observation)),
        statement="the B7 detour is consistent with a closed gap",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "associated"
    assert "reconstructed_input" in outcome.claim.qualifiers

    # And a claim citing nothing but recorded evidence is unaffected.
    assert run().claim is not None
    assert run().claim.level == "mechanism_verified"  # type: ignore[union-attr]


def test_a_deterministic_but_correlational_tool_stops_at_associated() -> None:
    latency_proposal = proposal(
        hypothesis_id="hyp-011",
        proposition_type="expansion_latency_association",
        proposed_subject="global_planner",
        supports=(EvidenceRef(ref="obs:latency_spike", kind="observation"),),
    )
    latency_result = CheckerResult(
        request_id="req-020",
        tool_id="latency_vs_expanded_nodes",
        tool_version="1.0.0",
        execution_status="completed",
        input_provenance="recorded",
        proposition_verdict="supported",
        supported_propositions=(
            PropositionOutcome(
                proposition_id="latency_tracks_expansions",
                proposition_type="expansion_latency_association",
                result="supported",
            ),
        ),
        **SIGNATURE,
    )
    outcome = run(
        proposal=latency_proposal,
        record=record(proposal_ref="hyp-011", checker_results=(latency_result,)),
        statement="control latency co-occurs with node expansions",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "associated"


def test_no_applicable_check_leaves_the_hypothesis_resting_at_associated() -> None:
    outcome = run(
        record=record(checker_results=()),
        statement="the detour is consistent with a closed gap at B7",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "associated"
    assert "no_applicable_check:resting_at_associated" in outcome.reasons


def test_a_verified_mechanism_needs_an_execution_observation_to_stay_verified() -> None:
    """A verified condition that nobody observed being hit.

    The checker proves the geometry: the gap is narrower than the
    clearance. That the robot ever met that gap is a second statement,
    and a static fact does not make it. Without an execution
    observation the claim is true, unconnected to the outcome, and read
    as connected — so it drops to ``associated``.
    """
    outcome = run(
        proposal=proposal(supports=(GAP_FACT,)),
        statement="the B7 passage width was measured at 0.68 m",
    )
    assert outcome.claim is not None
    # Not ``associated`` either: with no observed behaviour there is
    # nothing for the mechanism to be consistent with, so what survives
    # is the measurement.
    assert outcome.claim.level == "observed"
    assert "mechanism_not_linked_to_outcome:no_execution_observation" in outcome.reasons


def test_a_verified_mechanism_needs_an_impact_ref_to_stay_verified() -> None:
    """Verified, observed, and still not tied to the utility gap."""
    outcome = run(
        record=record(impact_ref=None),
        statement="the B7 passage is consistent with a closed gap",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "associated"
    assert "mechanism_not_linked_to_outcome:no_impact_ref" in outcome.reasons


def test_a_hypothesis_with_no_behavioural_pattern_is_not_a_claim() -> None:
    outcome = run(
        proposal=proposal(supports=(GAP_FACT,)),
        record=record(checker_results=()),
        statement="the B7 passage is consistent with a closed gap",
    )
    assert not outcome.promoted
    assert "no_pattern_evidence" in outcome.reasons


def test_a_preregistered_intervention_is_the_only_route_to_the_top_rung() -> None:
    outcome = run(
        record=record(evidence_lane="research", intervention=intervention()),
        statement="widening the B7 passage eliminates the difference",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "intervention_supported"
    assert "research_lane" in outcome.claim.qualifiers


def test_an_intervention_on_another_axis_does_not_promote_this_proposition() -> None:
    """The failure a bare preregistration+scope object allowed.

    Varying the controller's sampling budget and finding an effect says
    nothing about a costmap inflation closing a gap, and the object used
    to be unable to tell the two apart.
    """
    elsewhere = intervention(
        axes=("dwa_vx_samples",),
        proposition_type="local_minimum_entrapment",
        subject="local_controller",
    )
    outcome = run(
        record=record(evidence_lane="research", intervention=elsewhere),
        statement="widening the B7 passage eliminates the difference",
    )
    assert not outcome.promoted
    assert "intervention_tests_another_proposition:local_minimum_entrapment" in outcome.reasons

    other_subject = intervention(subject="global_planner")
    outcome = run(
        record=record(evidence_lane="research", intervention=other_subject),
        statement="widening the B7 passage eliminates the difference",
    )
    assert not outcome.promoted
    assert "intervention_acts_on_another_subject:global_planner" in outcome.reasons


def test_an_intervention_that_found_nothing_refuses_rather_than_falls_back() -> None:
    for verdict, reason in (
        ("refuted", "refuted_by_intervention:prereg-07"),
        ("inconclusive", "intervention_inconclusive:prereg-07"),
    ):
        outcome = run(
            record=record(
                evidence_lane="research",
                intervention=intervention(verdict=verdict, effect_direction="reduced"),
            ),
            statement="widening the B7 passage eliminates the difference",
        )
        assert not outcome.promoted
        assert reason in outcome.reasons


def test_an_intervention_claim_must_be_spoken_inside_the_scope_it_was_run_in() -> None:
    outcome = run(
        record=record(
            evidence_lane="research",
            intervention=intervention(scope="simulator, declared Task Neighborhood"),
        ),
        scope="everywhere",
        statement="widening the B7 passage eliminates the difference",
    )
    assert not outcome.promoted
    assert any(reason.startswith("scope_mismatch") for reason in outcome.reasons)


# --------------------------------------------------------------------------
# What kills a claim
# --------------------------------------------------------------------------


def test_one_refuting_check_kills_the_claim_however_many_supported_it() -> None:
    outcome = run(
        record=record(
            checker_results=(gap_result(), gap_result(verdict="refuted")),
        )
    )
    assert not outcome.promoted
    assert "refuted_by:gap_vs_footprint@1.0.0" in outcome.reasons


def test_a_known_unknown_blocks_the_claim_type_it_names() -> None:
    blocker = KnownUnknown(
        id="inflation_implementation_unknown",
        blocks_claim_types=("geometric_infeasibility",),
        source="h4_not_complete",
    )
    outcome = run(known_unknowns=[blocker])
    assert not outcome.promoted
    assert outcome.reasons == ("blocked_by_known_unknown:inflation_implementation_unknown",)


def test_an_unadjudicated_record_produces_nothing() -> None:
    for status in ("proposed", "check_failed", "not_checkable"):
        outcome = run(record=record(status=status, checker_results=()))
        assert not outcome.promoted
        assert outcome.reasons == (f"record_status:{status}",)


def test_a_result_from_a_tool_nobody_declared_is_refused() -> None:
    stranger = CheckerResult(
        request_id="req-099",
        tool_id="gap_vs_footprint",
        tool_version="9.9.9",
        execution_status="completed",
        input_provenance="recorded",
        proposition_verdict="supported",
        supported_propositions=(
            PropositionOutcome(
                proposition_id="p",
                proposition_type="geometric_infeasibility",
                result="supported",
            ),
        ),
        **SIGNATURE,
    )
    outcome = run(record=record(checker_results=(stranger,)))
    assert not outcome.promoted
    assert "unknown_tool:gap_vs_footprint@9.9.9" in outcome.reasons


def test_a_result_reaching_past_its_card_contributes_nothing() -> None:
    overreach = CheckerResult(
        request_id="req-100",
        tool_id="latency_vs_expanded_nodes",
        tool_version="1.0.0",
        execution_status="completed",
        input_provenance="recorded",
        proposition_verdict="supported",
        supported_propositions=(
            PropositionOutcome(
                proposition_id="p",
                proposition_type="geometric_infeasibility",
                result="supported",
            ),
        ),
        **SIGNATURE,
    )
    outcome = run(
        record=record(checker_results=(overreach,)),
        statement="the detour is consistent with a closed gap at B7",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "associated"
    assert any("result_exceeds_card" in reason for reason in outcome.reasons)


def test_a_card_that_forbids_the_proposition_refuses_it_by_name() -> None:
    latency_proposal = proposal(
        hypothesis_id="hyp-012",
        proposition_type="candidate_latency_attribution",
        proposed_subject="global_planner",
        supports=(EvidenceRef(ref="obs:latency_spike", kind="observation"),),
    )
    result = CheckerResult(
        request_id="req-021",
        tool_id="latency_vs_expanded_nodes",
        tool_version="1.0.0",
        execution_status="completed",
        input_provenance="recorded",
        proposition_verdict="supported",
        supported_propositions=(
            PropositionOutcome(
                proposition_id="p",
                proposition_type="candidate_latency_attribution",
                result="supported",
            ),
        ),
        **SIGNATURE,
    )
    outcome = run(
        proposal=latency_proposal,
        record=record(proposal_ref="hyp-012", checker_results=(result,)),
        statement="the candidate's own compute co-occurs with the latency",
    )
    assert not outcome.promoted
    assert (
        "forbidden_inference:latency_vs_expanded_nodes@1.0.0:candidate_latency_attribution"
        in outcome.reasons
    )


def test_a_check_that_could_not_run_contributes_nothing_but_does_not_refute() -> None:
    outcome = run(
        record=record(checker_results=(gap_result(status="not_checkable"),)),
        statement="the detour is consistent with a closed gap at B7",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "associated"
    assert "gap_vs_footprint@1.0.0:execution_status=not_checkable" in outcome.reasons


def test_the_subject_ceiling_outranks_a_perfectly_good_check() -> None:
    perception = proposal(
        hypothesis_id="hyp-013",
        proposition_type="geometric_infeasibility",
        proposed_subject="perception_provider",
    )
    outcome = run(
        proposal=perception,
        record=record(proposal_ref="hyp-013"),
        statement="the B7 passage width was measured at 0.68 m",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "observed"


def test_a_record_about_another_proposal_is_refused() -> None:
    outcome = run(record=record(proposal_ref="hyp-999"))
    assert not outcome.promoted
    assert any(reason.startswith("record_proposal_mismatch") for reason in outcome.reasons)


def test_causal_wording_is_refused_even_when_the_evidence_is_good() -> None:
    outcome = run(statement="the detour happened because of the closed gap at B7")
    assert not outcome.promoted
    assert "forbidden_phrase_at_mechanism_verified:because of" in outcome.reasons


# --------------------------------------------------------------------------
# Qualifiers, measurements, determinism
# --------------------------------------------------------------------------


def test_an_estimated_profile_weighted_impact_qualifies_the_claim() -> None:
    impact = ImpactRef(
        artifact_ref="artifacts/explain/impact_detour_excision.json",
        impact_kind="attributable_effect_estimate",
        objective="time_efficiency",
        method="detour_excision",
        assumptions=("the excised segment is otherwise nominal",),
        uncertainty="paired bootstrap CI",
        profile_weighted=True,
    )
    outcome = run(record=record(impact_ref=impact))
    assert outcome.claim is not None
    assert outcome.claim.qualifiers == ("estimated", "profile_weighted")
    assert outcome.claim.impact_ref is impact


def test_a_measurement_is_a_claim_without_an_analyst() -> None:
    outcome = promote_measurement(
        claim_id="claim-0",
        proposition_type="geometric_infeasibility",
        subject="task_geometry",
        statement="the narrowest passage on the route was measured at 0.68 m",
        scope=SCOPE,
        supports=(GAP_FACT,),
        record_ref="rec-0",
    )
    assert outcome.claim is not None
    assert outcome.claim.level == "observed"

    reconstructed = promote_measurement(
        claim_id="claim-0",
        proposition_type="geometric_infeasibility",
        subject="task_geometry",
        statement="the narrowest passage on the route was measured at 0.68 m",
        scope=SCOPE,
        supports=(EvidenceRef(ref="fact:gap", kind="fact", provenance="reconstructed"),),
        record_ref="rec-0",
    )
    assert not reconstructed.promoted
    assert reconstructed.reasons == ("measurement_requires_recorded_evidence",)


def test_the_matrix_is_deterministic() -> None:
    assert run().model_dump() == run().model_dump()


@pytest.mark.parametrize("statement", ["", "   "])
def test_an_empty_statement_never_becomes_a_claim(statement: str) -> None:
    outcome = run(statement=statement)
    assert not outcome.promoted
    assert outcome.reasons == ("empty_statement",)
