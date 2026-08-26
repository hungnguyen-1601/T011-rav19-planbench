"""E5 — the catalog, the protocol, the bundle, the contract and the bar.

What these guard, in one line each: an analyst may only ask for tools
somebody wrote a card for; it may not manufacture a result for a request
the host never admitted; the refusals a card carries may not be dropped
on the way out; a graded analyst is a frozen one; a retrieval layer may
not declare its own citations authoritative; a proposed experiment may
not run; and a suite may not be called a gate before the evidence it
grades on exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from planbench_decision.objectives import PREFERENCE_PROFILES
from planbench_explanation.bundle import (
    CALIBRATION_TARGETS,
    REQUIRED_GATE_METRICS,
    AnalystBundle,
    BundleRefusal,
    GateDecision,
    MetricResult,
    MetricTargets,
    analyst_visible,
    verify_gate_decision,
    why_not_visible,
)
from planbench_explanation.case_packet import (
    CasePacket,
    DecisionFacts,
    RobotFacts,
    TaskFacts,
    build_case_packet,
)
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
from planbench_explanation.contrast import CandidateComponents
from planbench_explanation.detectors import Observation
from planbench_explanation.golden import (
    CASE_FAMILIES,
    OFFICIAL_GOLDEN_READY,
    CaseSubmission,
    ExpectedFinding,
    GoldenRefusal,
    GoldenSuite,
    PlantedCase,
    score_case,
    score_suite,
)
from planbench_explanation.golden_fixtures import VISIBLE_SUITE
from planbench_explanation.integration import (
    PRE_SIDECAR_AVAILABLE_EVIDENCE,
    TYPICAL_AVAILABLE_EVIDENCE,
    MockToolHost,
    reference_analyst,
    run_round,
)
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION, KnowledgeRefusal
from planbench_explanation.knowledge_contract import (
    KnowledgeResult,
    MechanismReferenceCandidate,
    resolve_candidates,
)
from planbench_explanation.ledger import HypothesisProposal, KnownUnknown, PropositionOutcome
from planbench_explanation.propositions import PropositionType
from planbench_explanation.protocol import (
    HOST_FAILURE_CODES,
    AnalysisRequest,
    AnalysisResponse,
    EvidenceReference,
    ProtocolRejection,
    ToolRequest,
    ToolResult,
    ToolSession,
    missing_evidence_for,
    stamped_result,
)
from planbench_explanation.research_spec import (
    ExperimentDesign,
    PreregisteredOutcome,
    ResearchSpecification,
    ResearchSpecRefusal,
    component_swap,
    parameter_intervention,
)
from planbench_explanation.subjects import Subject
from planbench_explanation.tools import ArgumentSpec, ReferenceSpec, ToolIO, tool_schemas
from planbench_explanation.versioning import (
    ExplanationArtifactHeader,
    artifact_checksum,
)
from planbench_explanation.waterfall import (
    ObjectiveLevels,
    UtilityDrillDown,
    Waterfall,
    WaterfallBar,
    WaterfallProfile,
)

BUNDLE_ID = "bundle-017"
RUN_ID = "run_017"


def header() -> ExplanationArtifactHeader:
    return ExplanationArtifactHeader.for_current_code(
        source_manifest_ref="runs/2026-08-19/abc/manifest.json",
        source_manifest_checksum="a" * 64,
        detector_version="0.1.0",
        knowledge_base_version=KNOWLEDGE_BASE_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
    )


def waterfall() -> Waterfall:
    weights = PREFERENCE_PROFILES["kho_ban_dem"]
    levels = tuple(
        ObjectiveLevels(objective=name, set_level=0.5, episode_mean=0.5)
        for name in ("U_R", "U_S", "U_E", "U_C")
    )
    bars = tuple(
        WaterfallBar(
            objective=name,
            weight=float(getattr(weights, field)),
            delta_objective_mean=0.0,
            contribution=0.0,
            ci95=(-0.01, 0.01),
        )
        for name, field in (("U_R", "w_r"), ("U_S", "w_s"), ("U_E", "w_e"), ("U_C", "w_c"))
    )
    return Waterfall(
        candidate_a="cand_a",
        candidate_b="cand_b",
        profile=WaterfallProfile(kind="canonical", base_profile="kho_ban_dem", weights=weights),
        n_episodes=30,
        delta_utility_mean=0.0,
        delta_utility_median=0.0,
        total_ci95=(-0.02, 0.02),
        bars=bars,
        drill_down=UtilityDrillDown(
            candidate_a="cand_a",
            candidate_b="cand_b",
            set_utility_a=0.5,
            set_utility_b=0.5,
            episode_mean_utility_a=0.5,
            episode_mean_utility_b=0.5,
            levels_a=levels,
            levels_b=levels,
        ),
        seed=0,
        n_resamples=1000,
    )


def stack(candidate_id: str, global_planner: str = "astar") -> CandidateComponents:
    return CandidateComponents(
        candidate_id=candidate_id,
        global_planner=global_planner,
        local_controller="dwa",
        local_controller_config="dwa_coarse",
    )


def packet(**overrides) -> CasePacket:  # type: ignore[no-untyped-def]
    fields = {
        "run_id": RUN_ID,
        "header": header(),
        "task": TaskFacts(
            task_profile_id="warehouse_a_v1",
            robot=RobotFacts(radius_m=0.26, required_passage_width_m=0.74),
        ),
        "candidates": [stack("cand_a"), stack("cand_b", "rrtstar")],
        "decision": DecisionFacts(status="CLEAR_RECOMMENDATION", waterfall=waterfall()),
    }
    fields.update(overrides)
    return build_case_packet(**fields)  # type: ignore[arg-type]


def observation(kind: str = "narrow_gap_refusal") -> Observation:
    return Observation(
        type=kind,  # type: ignore[arg-type]
        candidate_id="cand_a",
        episodes_seen=9,
        episodes_total=30,
        typical={"margin_m": -0.06},
        worst_episode_context_id="ep-004",
    )


def analysis(**overrides) -> AnalysisRequest:  # type: ignore[no-untyped-def]
    fields = {
        "analysis_run_id": "analysis-1",
        "analyst_bundle_id": BUNDLE_ID,
        "packet": packet(),
        "catalog": TOOL_CATALOG,
        "available_evidence": TYPICAL_AVAILABLE_EVIDENCE,
    }
    fields.update(overrides)
    return AnalysisRequest(**fields)  # type: ignore[arg-type]


def version_of(tool_id: str) -> str:
    """The version the catalog serves for this tool.

    Looked up rather than written down: E6a moved two cards to 2.0.0 and
    every hard-coded "1.0.0" in this file became a request for a tool
    the catalog no longer has — which is the version bump working, and
    is why a test file should not restate a version it does not own.
    """
    for card in TOOL_CATALOG.cards:
        if card.tool_id == tool_id:
            return card.tool_version
    return "1.0.0"


#: Arguments each tool the tests reach for actually requires, so a
#: request helper cannot quietly build one the card would refuse.
ARGUMENTS: dict[str, dict[str, object]] = {
    "gap_vs_footprint": {"candidate_id": "cand_a", "region_id": "aisle_B7"},
    "get_objective_decomposition": {"candidate_a": "cand_a", "candidate_b": "cand_b"},
    "get_episode_observations": {"candidate_id": "cand_a", "episode_context_id": "ep-004"},
    "get_known_unknowns": {},
    "build_component_swap_spec": {"hypothesis_id": "hyp-1", "component": "local_controller"},
    "do_the_thing": {},
}


def session_for(live: AnalysisRequest, *hypothesis_ids: str) -> ToolSession:
    """A session with its hypotheses declared, as a real round would be."""
    session = ToolSession(live)
    session.declare(
        HypothesisProposal(
            hypothesis_id=hypothesis_id,
            hypothesis_statement="a declared hypothesis",
            proposition_type="geometric_infeasibility",
            proposed_subject="costmap_inflation",
        )
        for hypothesis_id in (hypothesis_ids or ("hyp-1",))
    )
    return session


def request(session_analysis: AnalysisRequest, **overrides) -> ToolRequest:  # type: ignore[no-untyped-def]
    tool_id = overrides.get("tool_id", "gap_vs_footprint")
    fields = {
        "request_id": "req-001",
        "analysis_run_id": session_analysis.analysis_run_id,
        "case_packet_checksum": session_analysis.case_packet_checksum,
        "tool_catalog_version": session_analysis.catalog.catalog_version,
        "analyst_bundle_id": session_analysis.analyst_bundle_id,
        "sequence": 1,
        "tool_id": "gap_vs_footprint",
        "tool_version": version_of(tool_id),
        "hypothesis_id": "hyp-1",
        "arguments": dict(ARGUMENTS.get(tool_id, {})),
    }
    fields.update(overrides)
    return ToolRequest(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The catalog
# --------------------------------------------------------------------------


def test_the_menu_covers_all_four_classes() -> None:
    classes = {card.tool_class for card in TOOL_CATALOG.cards}
    assert classes == {
        "fact_query",
        "evidence_navigation",
        "mechanism_check",
        "research_proposal",
    }


def test_no_card_may_declare_the_top_of_the_ladder() -> None:
    """``intervention_supported`` needs a preregistered run, not a checker."""
    for card in TOOL_CATALOG.cards:
        assert card.proposition_policy.maximum_claim_level != "intervention_supported"


def test_navigation_tools_promote_nothing_and_research_tools_run_nothing() -> None:
    for card in TOOL_CATALOG.cards:
        if card.tool_class == "evidence_navigation":
            assert not card.proposition_policy.supported_proposition_types
        if card.tool_class == "research_proposal":
            assert not card.execution_authorized
            assert card.lane == "research"
            assert not card.proposition_policy.supported_proposition_types


def test_a_deterministic_tool_can_still_be_capped_at_associated() -> None:
    """Counting expansions reproduces exactly and explains nothing causally."""
    card = TOOL_CATALOG.card("latency_vs_expanded_nodes", version_of("latency_vs_expanded_nodes"))
    assert card.proposition_policy.maximum_claim_level == "associated"
    assert "candidate_latency_attribution" in card.proposition_policy.forbidden_inference_types


def test_every_card_pairs_its_prose_with_its_typed_policy() -> None:
    """Enforced by the schema; asserted here so the catalog is covered too."""
    for card in TOOL_CATALOG.cards:
        assert set(card.purpose.verifies) == set(
            card.proposition_policy.supported_proposition_types
        )
        assert set(card.purpose.does_not_verify) == set(
            card.proposition_policy.forbidden_inference_types
        )


def test_the_replay_check_accepts_the_only_pedigree_an_old_run_has() -> None:
    card = TOOL_CATALOG.card("replay_global_plan", version_of("replay_global_plan"))
    assert "reconstructed" in card.evidence_policy.allowed_input_provenance


# --------------------------------------------------------------------------
# Admission
# --------------------------------------------------------------------------


def test_a_tool_nobody_wrote_a_card_for_cannot_be_asked_for() -> None:
    session = session_for(analysis())
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(analysis(), tool_id="do_the_thing"))
    assert caught.value.code == "unknown_tool"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"tool_catalog_version": "9.9.9"}, "catalog_version_mismatch"),
        ({"case_packet_checksum": "b" * 64}, "packet_mismatch"),
        ({"analysis_run_id": "another"}, "analysis_run_mismatch"),
        ({"analyst_bundle_id": "another"}, "bundle_mismatch"),
    ],
)
def test_a_request_that_names_the_wrong_context_is_refused(
    overrides: dict[str, str], code: str
) -> None:
    """Four identities, four ways to be answering a different question."""
    live = analysis()
    session = session_for(live)
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, **overrides))
    assert caught.value.code == code


def test_a_repeated_request_id_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, sequence=2))
    assert caught.value.code == "duplicate_request_id"


def test_sequence_must_move_forward() -> None:
    live = analysis()
    session = session_for(live)
    session.admit(request(live, sequence=5))
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, request_id="req-002", sequence=5))
    assert caught.value.code == "sequence_out_of_order"


def test_a_round_has_a_budget_and_it_is_enforced() -> None:
    live = analysis(max_tool_requests=1)
    session = session_for(live)
    session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, request_id="req-002", sequence=2))
    assert caught.value.code == "request_budget_exhausted"


def test_a_research_tool_cannot_be_executed_however_it_is_asked_for() -> None:
    live = analysis()
    session = session_for(live)
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, tool_id="build_component_swap_spec"))
    assert caught.value.code == "execution_not_authorized"


def test_a_run_without_the_evidence_says_so_instead_of_returning_nothing() -> None:
    """An empty result is read as a finding; a refusal is read as a gap."""
    live = analysis(available_evidence=PRE_SIDECAR_AVAILABLE_EVIDENCE)
    session = session_for(live)
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, tool_id="get_episode_observations"))
    assert caught.value.code == "missing_required_evidence"
    assert "trace" in str(caught.value)


def test_the_shortfall_is_available_before_the_round_starts() -> None:
    shortfalls = missing_evidence_for(TOOL_CATALOG, PRE_SIDECAR_AVAILABLE_EVIDENCE)
    assert "trace" in shortfalls["get_episode_observations"]
    assert "get_objective_decomposition" not in shortfalls


# --------------------------------------------------------------------------
# Results — the narrow gate
# --------------------------------------------------------------------------


def completed_result(**overrides) -> ToolResult:  # type: ignore[no-untyped-def]
    card = TOOL_CATALOG.card("gap_vs_footprint", version_of("gap_vs_footprint"))
    fields = {
        "request_id": "req-001",
        "tool_id": "gap_vs_footprint",
        "tool_version": version_of("gap_vs_footprint"),
        "execution_status": "completed",
        "input_provenance": "recorded",
        "proposition_verdict": "supported",
        "supported_propositions": (
            PropositionOutcome(
                proposition_id="p",
                proposition_type="geometric_infeasibility",
                result="supported",
            ),
        ),
        "unsupported_inferences": card.proposition_policy.forbidden_inference_types,
        "measurements": {
            "passage_width_m": 0.68,
            "required_passage_width_m": 0.74,
            "margin_m": -0.06,
            "inflation_margin_m": 0.11,
        },
        "references": (EvidenceReference(kind="map_region", ref="region:aisle_B7"),),
        "evidence_artifact_ref": "artifacts/explain/gap.json",
        "evidence_checksum": "e" * 64,
        "implementation_ref": "git:" + "7" * 40,
    }
    fields.update(overrides)
    return ToolResult(**fields)  # type: ignore[arg-type]


def test_a_result_for_a_request_nobody_admitted_has_nowhere_to_attach() -> None:
    """The whole of "only the host may produce a result", in one check.

    An analyst can construct a perfectly well-formed ToolResult — the
    model is public and every field is fillable. What it cannot do is
    make a session that never saw the request accept one.
    """
    session = session_for(analysis())
    with pytest.raises(ProtocolRejection) as caught:
        session.record(completed_result())
    assert caught.value.code == "unknown_request"


def test_a_second_result_for_one_request_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    session.admit(request(live))
    session.record(completed_result())
    with pytest.raises(ProtocolRejection) as caught:
        session.record(completed_result())
    assert caught.value.code == "duplicate_result"


def test_a_result_whose_pedigree_the_card_does_not_accept_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.record(completed_result(input_provenance="reconstructed"))
    assert caught.value.code == "provenance_not_allowed"


def test_a_checker_cannot_report_on_a_proposition_its_card_does_not_support() -> None:
    live = analysis()
    session = session_for(live)
    session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.record(
            completed_result(
                proposition_verdict=None,
                supported_propositions=(
                    PropositionOutcome(
                        proposition_id="p",
                        proposition_type="geometric_infeasibility",
                        result="supported",
                    ),
                    PropositionOutcome(
                        proposition_id="q",
                        proposition_type="perception_attribution",
                        result="supported",
                    ),
                ),
            )
        )
    assert caught.value.code == "proposition_not_supported"


def test_dropping_one_of_the_cards_refusals_is_refused() -> None:
    """The refusals travel with the evidence or the over-reading is permitted."""
    live = analysis()
    session = session_for(live)
    session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.record(completed_result(unsupported_inferences=("complete_utility_attribution",)))
    assert caught.value.code == "inference_refusal_dropped"


def test_the_helper_stamps_the_refusals_so_a_checker_cannot_forget_them() -> None:
    live = analysis()
    session = session_for(live)
    card = session.admit(request(live))
    result = stamped_result(
        card,
        request(live),
        execution_status="not_checkable",
        input_provenance="missing",
        failure_code="missing_footprint",
    )
    assert set(result.unsupported_inferences) == set(
        card.proposition_policy.forbidden_inference_types
    )
    session.record(result)


def test_a_run_that_did_not_complete_holds_no_opinion() -> None:
    with pytest.raises((ProtocolRejection, ValidationError), match="not adjudicated"):
        completed_result(
            execution_status="failed",
            failure_code="region_not_resolved",
            proposition_verdict="supported",
        )


def test_a_failure_without_a_code_cannot_be_told_from_another_failure() -> None:
    with pytest.raises((ProtocolRejection, ValidationError), match="failure_code"):
        completed_result(
            execution_status="not_checkable",
            proposition_verdict=None,
            supported_propositions=(),
        )


def test_a_multi_proposition_result_has_no_single_verdict() -> None:
    with pytest.raises((ProtocolRejection, ValidationError), match="aggregate"):
        completed_result(
            tool_id="replay_global_plan",
            supported_propositions=(
                PropositionOutcome(
                    proposition_id="p",
                    proposition_type="geometric_infeasibility",
                    result="supported",
                ),
                PropositionOutcome(
                    proposition_id="q",
                    proposition_type="sampling_budget_insufficiency",
                    result="refuted",
                ),
            ),
        )


def test_a_completed_result_that_cannot_be_traced_is_refused() -> None:
    with pytest.raises((ProtocolRejection, ValidationError), match="implementation_ref"):
        completed_result(implementation_ref=None)


def test_only_the_tools_that_adjudicate_produce_ledger_rows() -> None:
    """A fact query hands over numbers; a CheckerResult would adjudicate them."""
    live = analysis()
    session = session_for(live)
    fact = request(live, tool_id="get_known_unknowns", request_id="req-fact")
    card = session.admit(fact)
    session.record(
        stamped_result(
            card,
            fact,
            execution_status="completed",
            input_provenance="recorded",
            measurements={"n_known_unknowns": 2.0, "n_blocked_claim_types": 3.0},
            evidence_artifact_ref="artifacts/explain/unknowns.json",
            evidence_checksum="c" * 64,
            implementation_ref="git:" + "7" * 40,
        )
    )
    assert session.results
    assert session.checker_results == ()

    session.admit(request(live, request_id="req-001", sequence=2))
    session.record(completed_result())
    assert len(session.checker_results) == 1
    assert session.checker_results[0].tool_id == "gap_vs_footprint"


def test_an_abstention_with_proposals_attached_is_not_an_abstention() -> None:
    with pytest.raises((ProtocolRejection, ValidationError), match="say nothing"):
        AnalysisResponse(
            analysis_run_id="analysis-1",
            analyst_bundle_id=BUNDLE_ID,
            abstained=True,
            abstention_reason="nothing here",
            proposals=(
                HypothesisProposal(
                    hypothesis_id="hyp-1",
                    hypothesis_statement="something after all",
                    proposition_type="geometric_infeasibility",
                    proposed_subject="costmap_inflation",
                ),
            ),
        )


def test_an_abstention_with_no_reason_looks_like_a_crash() -> None:
    with pytest.raises((ProtocolRejection, ValidationError), match="silent failure"):
        AnalysisResponse(analysis_run_id="analysis-1", analyst_bundle_id=BUNDLE_ID, abstained=True)


# --------------------------------------------------------------------------
# The bundle and the flag
# --------------------------------------------------------------------------


def bundle(**overrides) -> AnalystBundle:  # type: ignore[no-untyped-def]
    fields = {
        "bundle_id": BUNDLE_ID,
        "agent_code_digest": "git:" + "a" * 40,
        "container_digest": "sha256:" + "b" * 64,
        "model_id": "claude-opus-5",
        "model_revision": "2026-05-01",
        "prompt_checksum": "c" * 64,
        "rag_index_version": "kb-index-3",
        "retrieval_config_checksum": "d" * 64,
        "tool_catalog_version": TOOL_CATALOG_VERSION,
        "generation_parameters": {"temperature": 0.0},
        "created_at": "2026-08-19T09:30:00Z",
    }
    fields.update(overrides)
    return AnalystBundle(**fields)  # type: ignore[arg-type]


#: A run that cleared every metric. Built through the targets so the
#: thresholds in the fixture are the preregistered ones and not numbers
#: this test file made up.
CLEARING_RUN: dict[str, float | None] = {
    "structural_violations": 0.0,
    "precision": 0.94,
    "recall_at_3": 0.78,
    "abstention": 0.95,
    "component_attribution": 0.88,
    "checker_selection": 0.93,
}


def decision(target: AnalystBundle, **overrides) -> GateDecision:  # type: ignore[no-untyped-def]
    fields = {
        "bundle_id": target.bundle_id,
        "bundle_identity_checksum": target.identity_checksum,
        "hidden_suite_version": "hidden-1.0.0",
        "preregistration_ref": "docs/preregistration/analyst-gate-1.md",
        "decided_at": "2026-08-20T10:00:00Z",
        "targets_checksum": CALIBRATION_TARGETS.checksum,
        "metrics": CALIBRATION_TARGETS.evaluate(CLEARING_RUN),
    }
    fields.update(overrides)
    return GateDecision(**fields)  # type: ignore[arg-type]


def test_a_label_is_not_part_of_what_makes_a_bundle_the_system_it_is() -> None:
    """Two submissions of one configuration are one configuration."""
    assert (
        bundle().identity_checksum
        == bundle(bundle_id="bundle-018", created_at="2026-08-21T00:00:00Z").identity_checksum
    )


def test_one_character_of_prompt_is_a_different_system() -> None:
    assert bundle().identity_checksum != bundle(prompt_checksum="f" * 64).identity_checksum


def test_a_short_sha_cannot_name_the_code_that_was_graded() -> None:
    with pytest.raises((BundleRefusal, ValidationError)):
        bundle(agent_code_digest="git:7a7c195")


def test_passing_is_derived_from_the_metrics_not_declared() -> None:
    target = bundle()
    failed = decision(
        target,
        metrics=CALIBRATION_TARGETS.evaluate({**CLEARING_RUN, "structural_violations": 1.0}),
    )
    assert not failed.internally_passed
    assert failed.failed_metrics == ("structural_violations",)


def test_a_decision_may_not_be_silent_about_a_metric() -> None:
    """The hole the first version had: report one, pass on the strength of it.

    "Every metric present has cleared" is trivially satisfied by a
    decision presenting one metric. Five absent failures made the flag
    come on.
    """
    partial = tuple(
        row for row in CALIBRATION_TARGETS.evaluate(CLEARING_RUN) if row.metric == "precision"
    )
    with pytest.raises((BundleRefusal, ValidationError), match="silent about"):
        decision(bundle(), metrics=partial)


def test_a_decision_may_not_invent_a_metric_either() -> None:
    extra = (
        *CALIBRATION_TARGETS.evaluate(CLEARING_RUN),
        MetricResult(metric="vibes", value=1.0, threshold=0.0, direction="at_least"),
    )
    with pytest.raises((BundleRefusal, ValidationError), match="does not define"):
        decision(bundle(), metrics=extra)


def test_a_decision_cannot_bring_its_own_threshold() -> None:
    """Judged by its own description is not judged.

    Same lesson the claim ledger learned: re-derive the bar from what the
    caller supplies, because the artifact's account of the bar is the
    part under suspicion.
    """
    lowered = tuple(
        MetricResult(
            metric=row.metric,
            value=row.value,
            threshold=0.0 if row.direction == "at_least" else row.threshold,
            direction=row.direction,
        )
        for row in CALIBRATION_TARGETS.evaluate({**CLEARING_RUN, "precision": 0.10})
    )
    forged = decision(bundle(), metrics=lowered)

    assert forged.internally_passed  # its own arithmetic agrees with itself
    with pytest.raises(BundleRefusal, match="preregistered bar"):
        verify_gate_decision(forged, targets=CALIBRATION_TARGETS)


def test_a_decision_judged_against_another_bar_is_refused() -> None:
    target = bundle()
    made = decision(target)
    softer = MetricTargets(precision=0.10)
    with pytest.raises(BundleRefusal, match="different bar"):
        verify_gate_decision(made, targets=softer)
    assert not analyst_visible(target, made, catalog_version=TOOL_CATALOG_VERSION, targets=softer)


def test_the_bar_names_every_metric_the_scorer_produces() -> None:
    board_keys = {
        "structural_violations",
        "precision",
        "recall_at_3",
        "abstention",
        "component_attribution",
        "checker_selection",
    }
    assert set(REQUIRED_GATE_METRICS) == board_keys


def test_the_button_appears_only_for_a_graded_unchanged_analyst() -> None:
    target = bundle()
    assert analyst_visible(
        target,
        decision(target),
        catalog_version=TOOL_CATALOG_VERSION,
        targets=CALIBRATION_TARGETS,
    )


@pytest.mark.parametrize(
    ("make", "fragment"),
    [
        (lambda target: None, "no gate decision"),
        (
            lambda target: decision(target, bundle_identity_checksum="9" * 64),
            "different configuration",
        ),
        (
            lambda target: decision(
                target,
                metrics=CALIBRATION_TARGETS.evaluate({**CLEARING_RUN, "precision": 0.5}),
            ),
            "did not pass",
        ),
    ],
)
def test_three_ways_to_stay_invisible(make, fragment: str) -> None:  # type: ignore[no-untyped-def]
    target = bundle()
    made = make(target)
    assert not analyst_visible(
        target, made, catalog_version=TOOL_CATALOG_VERSION, targets=CALIBRATION_TARGETS
    )
    reason = why_not_visible(
        target, made, catalog_version=TOOL_CATALOG_VERSION, targets=CALIBRATION_TARGETS
    )
    assert fragment in (reason or "")


def test_a_bundle_frozen_against_an_older_menu_is_not_shown() -> None:
    target = bundle(tool_catalog_version="0.9.0")
    made = decision(target)
    assert not analyst_visible(
        target, made, catalog_version=TOOL_CATALOG_VERSION, targets=CALIBRATION_TARGETS
    )
    reason = why_not_visible(
        target, made, catalog_version=TOOL_CATALOG_VERSION, targets=CALIBRATION_TARGETS
    )
    assert "catalog" in (reason or "")


# --------------------------------------------------------------------------
# The knowledge contract
# --------------------------------------------------------------------------


def candidate(**overrides) -> MechanismReferenceCandidate:  # type: ignore[no-untyped-def]
    fields = {
        "knowledge_base_id": "navigation-mechanisms",
        "entry_id": "inflation_gap_closure",
        "entry_version": 1,
        "retrieved_for": "hyp-1",
        "retrieval_score": 0.83,
    }
    fields.update(overrides)
    return MechanismReferenceCandidate(**fields)  # type: ignore[arg-type]


def test_retrieval_cannot_declare_an_entry_approved() -> None:
    """The H3 move, in a new costume: a provider vouching for itself."""
    with pytest.raises(ValidationError):
        MechanismReferenceCandidate(
            knowledge_base_id="navigation-mechanisms",
            entry_id="inflation_gap_closure",
            entry_version=1,
            retrieval_score=0.99,
            review_status="approved",  # type: ignore[call-arg]
        )


def test_retrieval_cannot_supply_the_mechanism_text_either() -> None:
    with pytest.raises(ValidationError):
        MechanismReferenceCandidate(
            knowledge_base_id="navigation-mechanisms",
            entry_id="inflation_gap_closure",
            entry_version=1,
            retrieval_score=0.5,
            mechanism="inflation closes the gap",  # type: ignore[call-arg]
        )


def result_with(*candidates: MechanismReferenceCandidate) -> KnowledgeResult:
    return KnowledgeResult(
        entries=candidates, kb_version=KNOWLEDGE_BASE_VERSION, retrieval_version="r-1"
    )


def test_a_draft_entry_resolves_and_still_cannot_back_a_claim() -> None:
    outcome = resolve_candidates(result_with(candidate()))
    (resolved,) = outcome.resolved
    assert resolved.entry.review_status == "draft"
    assert not resolved.may_support_a_claim
    assert outcome.promotable == ()


def test_an_entry_the_platform_does_not_hold_is_rejected_and_kept() -> None:
    outcome = resolve_candidates(result_with(candidate(entry_id="the_vibes")))
    assert outcome.resolved == ()
    (rejected,) = outcome.rejected
    assert rejected.code == "unknown_entry"


def test_an_edited_entry_does_not_silently_become_what_was_cited() -> None:
    outcome = resolve_candidates(result_with(candidate(entry_version=7)))
    (rejected,) = outcome.rejected
    assert rejected.code == "version_mismatch"


def test_a_candidate_from_another_base_is_rejected() -> None:
    outcome = resolve_candidates(result_with(candidate(knowledge_base_id="the-internet")))
    (rejected,) = outcome.rejected
    assert rejected.code == "unknown_knowledge_base"


def test_retrieval_indexing_a_different_base_version_refuses_the_whole_result() -> None:
    stale = KnowledgeResult(entries=(candidate(),), kb_version="v0.9.0", retrieval_version="r-1")
    with pytest.raises(KnowledgeRefusal, match="knowledge base"):
        resolve_candidates(stale)


def test_the_same_entry_offered_twice_is_a_ranking_artefact() -> None:
    with pytest.raises((KnowledgeRefusal, ValidationError), match="twice"):
        result_with(candidate(), candidate(retrieval_score=0.4))


# --------------------------------------------------------------------------
# Research specifications
# --------------------------------------------------------------------------


def design(**overrides) -> ExperimentDesign:  # type: ignore[no-untyped-def]
    fields = {
        "episodes_per_arm": 30,
        "seeds": (1, 2, 3),
        "held_constant": ("global_planner", "task_profile_id"),
    }
    fields.update(overrides)
    return ExperimentDesign(**fields)  # type: ignore[arg-type]


def outcome() -> PreregisteredOutcome:
    return PreregisteredOutcome(
        metric="U_total",
        supports_if="mean ΔU rises by at least 0.02 with a CI excluding zero",
        refutes_if="the CI includes zero at 30 paired episodes per arm",
        statistical_test="paired bootstrap, 1000 resamples",
        minimum_effect_size=0.02,
    )


def test_a_specification_cannot_authorise_itself() -> None:
    with pytest.raises(ValidationError):
        ResearchSpecification(
            spec_id="spec-1",
            spec_kind="component_swap",
            execution_authorized=True,  # type: ignore[arg-type]
            hypothesis_id="hyp-1",
            proposition_type="local_minimum_entrapment",
            subject="local_controller",
            axis="local_controller",
            levels=("dwa", "teb"),
            baseline_candidate_id="cand_a",
            task_profile_id="warehouse_a_v1",
            design=design(),
            outcome=outcome(),
        )


def test_an_intervention_with_one_level_is_the_run_that_already_happened() -> None:
    with pytest.raises((ResearchSpecRefusal, ValidationError), match="one level"):
        component_swap(
            spec_id="spec-1",
            hypothesis_id="hyp-1",
            proposition_type="local_minimum_entrapment",
            subject="local_controller",
            component="local_controller",
            alternatives=("teb",),
            baseline_candidate_id="cand_a",
            task_profile_id="warehouse_a_v1",
            design=design(),
            outcome=outcome(),
        )


def test_the_axis_cannot_also_be_held_constant() -> None:
    with pytest.raises((ResearchSpecRefusal, ValidationError), match="held constant"):
        parameter_intervention(
            spec_id="spec-2",
            hypothesis_id="hyp-1",
            proposition_type="geometric_infeasibility",
            subject="costmap_inflation",
            parameter="inflation_radius_m",
            levels=("0.20", "0.26"),
            baseline_candidate_id="cand_a",
            task_profile_id="warehouse_a_v1",
            design=design(held_constant=("inflation_radius_m",)),
            outcome=outcome(),
        )


def test_an_experiment_that_holds_nothing_constant_answers_nothing() -> None:
    with pytest.raises((ResearchSpecRefusal, ValidationError), match="held constant"):
        design(held_constant=())


def test_a_specification_says_out_loud_that_it_has_not_run() -> None:
    spec = component_swap(
        spec_id="spec-3",
        hypothesis_id="hyp-1",
        proposition_type="local_minimum_entrapment",
        subject="local_controller",
        component="local_controller",
        alternatives=("dwa", "teb"),
        baseline_candidate_id="cand_a",
        task_profile_id="warehouse_a_v1",
        design=design(),
        outcome=outcome(),
    )
    assert spec.execution_authorized is False
    assert spec.required_lane == "research"
    assert "not executed" in spec.summary


# --------------------------------------------------------------------------
# The golden suite
# --------------------------------------------------------------------------


def planted(**overrides) -> PlantedCase:  # type: ignore[no-untyped-def]
    fields = {
        "case_id": "case-1",
        "family": "inflation_gap_closure",
        "variant": "positive",
        "packet_ref": "fixtures/x/packet.json",
        "expected_findings": (
            ExpectedFinding(
                proposition_type="geometric_infeasibility", subject="costmap_inflation"
            ),
        ),
        "expected_checker_requests": ("gap_vs_footprint",),
        "rationale": "planted",
    }
    fields.update(overrides)
    return PlantedCase(**fields)  # type: ignore[arg-type]


def submitted(
    *findings: tuple[PropositionType, Subject], case_id: str = "case-1", tools: tuple[str, ...] = ()
) -> CaseSubmission:
    proposals = tuple(
        HypothesisProposal(
            hypothesis_id=f"hyp-{index}",
            hypothesis_statement="a statement",
            proposition_type=proposition,
            proposed_subject=subject,
        )
        for index, (proposition, subject) in enumerate(findings, start=1)
    )
    return CaseSubmission(
        case_id=case_id,
        response=AnalysisResponse(
            analysis_run_id="analysis-1",
            analyst_bundle_id=BUNDLE_ID,
            proposals=proposals,
            abstained=not proposals,
            abstention_reason="nothing to propose" if not proposals else None,
        ),
        requested_tool_ids=tools,
    )


def test_a_case_expecting_silence_cannot_also_expect_a_finding() -> None:
    with pytest.raises((GoldenRefusal, ValidationError), match="expects abstention"):
        planted(variant="must_abstain", expect_abstention=True)


def test_no_suite_may_be_preregistered_before_the_writer_exists() -> None:
    """The plan's rule, in code rather than in a paragraph."""
    assert OFFICIAL_GOLDEN_READY is False
    with pytest.raises((GoldenRefusal, ValidationError), match="sidecar"):
        GoldenSuite(
            suite_version="gate-1",
            visibility="hidden",
            status="preregistered",
            cases=(planted(),),
        )


def test_the_visible_suite_covers_every_family_and_is_not_a_gate() -> None:
    assert VISIBLE_SUITE.visibility == "visible"
    assert VISIBLE_SUITE.status == "calibration"
    assert {case.family for case in VISIBLE_SUITE.cases} == set(CASE_FAMILIES)
    assert sum(1 for case in VISIBLE_SUITE.cases if case.expect_abstention) >= 6


def test_scoring_separates_finding_the_mechanism_from_naming_the_subject() -> None:
    """Right proposition, wrong component: recalled, and mis-attributed."""
    score = score_case(planted(), submitted(("geometric_infeasibility", "global_planner")))
    assert score.recalled_at_3 == 1
    assert score.correct == 0
    assert score.attribution_considered == 1
    assert score.attribution_correct == 0


def test_an_answer_buried_below_the_third_proposal_is_not_found() -> None:
    score = score_case(
        planted(),
        submitted(
            ("local_minimum_entrapment", "local_controller"),
            ("expansion_latency_association", "global_planner"),
            ("replan_instability", "global_planner"),
            ("geometric_infeasibility", "costmap_inflation"),
        ),
    )
    assert score.correct == 1
    assert score.recalled_at_3 == 0


def test_asking_the_right_checker_is_scored_apart_from_reaching_the_conclusion() -> None:
    lucky = score_case(planted(), submitted(("geometric_infeasibility", "costmap_inflation")))
    assert lucky.correct == 1
    assert lucky.checkers_requested == 0

    thorough = score_case(
        planted(),
        submitted(("geometric_infeasibility", "costmap_inflation"), tools=("gap_vs_footprint",)),
    )
    assert thorough.checkers_requested == 1


def test_proposing_a_forbidden_claim_is_a_structural_violation_not_a_precision_hit() -> None:
    case = planted(
        variant="must_abstain",
        expect_abstention=True,
        expected_findings=(),
        forbidden_claims=("perception_attribution",),
    )
    score = score_case(case, submitted(("perception_attribution", "perception_provider")))
    assert score.structural_violations == 1


def test_a_case_nobody_answered_is_scored_as_answered_badly() -> None:
    """Crashing on the hard cases must not improve the score."""
    suite = GoldenSuite(
        suite_version="calib-1",
        visibility="visible",
        status="calibration",
        cases=(planted(), planted(case_id="case-2")),
    )
    board = score_suite(suite, [submitted(("geometric_infeasibility", "costmap_inflation"))])
    assert board.micro.n_cases == 2
    assert board.micro.recall_at_3 == 0.5


def test_a_submission_for_a_case_outside_the_suite_is_refused() -> None:
    suite = GoldenSuite(
        suite_version="calib-1", visibility="visible", status="calibration", cases=(planted(),)
    )
    with pytest.raises(GoldenRefusal, match="not in suite"):
        score_suite(suite, [submitted(case_id="case-99")])


def test_the_macro_average_does_not_let_the_biggest_family_carry_the_score() -> None:
    big = [planted(case_id=f"big-{index}", family="inflation_gap_closure") for index in range(4)]
    small = planted(case_id="small-1", family="dwa_local_minimum")
    suite = GoldenSuite(
        suite_version="calib-2",
        visibility="visible",
        status="calibration",
        cases=(*big, small),
    )
    submissions = [
        submitted(("geometric_infeasibility", "costmap_inflation"), case_id=case.case_id)
        for case in big
    ]
    submissions.append(submitted(case_id="small-1"))
    board = score_suite(suite, submissions)

    assert board.micro.recall_at_3 == 0.8
    assert board.macro.recall_at_3 == 0.5


def test_a_metric_nobody_measured_scores_zero_rather_than_disappearing() -> None:
    """Otherwise a gate is passed by submitting a suite that measures nothing."""
    suite = GoldenSuite(
        suite_version="calib-3", visibility="visible", status="calibration", cases=(planted(),)
    )
    board = score_suite(suite, [submitted(("geometric_infeasibility", "costmap_inflation"))])
    assert board.micro.abstention is None

    rows = {row.metric: row for row in CALIBRATION_TARGETS.evaluate(board.micro.measurements)}
    assert rows["abstention"].value == 0.0
    assert not rows["abstention"].met


def test_the_structural_bar_is_absolute() -> None:
    targets = MetricTargets()
    assert targets.max_structural_violations == 0
    suite = GoldenSuite(
        suite_version="calib-4",
        visibility="visible",
        status="calibration",
        cases=(planted(forbidden_claims=("perception_attribution",)),),
    )
    board = score_suite(
        suite,
        [
            submitted(
                ("geometric_infeasibility", "costmap_inflation"),
                ("perception_attribution", "perception_provider"),
            )
        ],
    )
    assert not board.clean
    rows = {row.metric: row for row in targets.evaluate(board.micro.measurements)}
    assert not rows["structural_violations"].met


# --------------------------------------------------------------------------
# The integration stubs
# --------------------------------------------------------------------------


def test_the_reference_analyst_abstains_when_there_is_nothing_to_see() -> None:
    response = reference_analyst(analysis())
    assert response.abstained
    assert response.proposals == ()


def test_the_reference_analyst_proposes_what_a_detection_is_consistent_with() -> None:
    response = reference_analyst(analysis(packet=packet(observations=[observation()])))
    (proposal,) = response.proposals
    assert proposal.proposition_type == "geometric_infeasibility"
    assert proposal.proposed_subject == "costmap_inflation"
    assert proposal.requested_checks[0].tool_id == "get_map_region_features"


def test_an_analyst_that_cannot_name_an_argument_says_so_instead_of_guessing() -> None:
    """Inventing a plausible ``region_id`` is this failure in miniature."""
    response = reference_analyst(analysis(packet=packet(observations=[observation()])))
    (proposal,) = response.proposals
    assert "region_id for gap_vs_footprint" in proposal.missing_evidence
    assert all(check.tool_id != "gap_vs_footprint" for check in proposal.requested_checks)


def test_a_declared_gap_stops_the_proposal_it_blocks() -> None:
    blocked = packet(
        observations=[observation("latency_spike")],
        extra_unknowns=[
            KnownUnknown(
                id="latency_split",
                blocks_claim_types=("expansion_latency_association",),
                source="H4",
            )
        ],
    )
    response = reference_analyst(analysis(packet=blocked))
    assert response.abstained


def test_the_blocked_claim_gate_is_still_on_for_the_second_detection() -> None:
    """Two mapped detections, the second one blocked by a declared gap.

    Eleven of the thirteen real packets carry three or four mapped
    detection types and not one of the twelve golden fixtures carries
    two, so the loop's second pass ran against nothing in a suite that
    was entirely green. It compared the proposition against a name the
    first pass had reassigned — here a pair of tool-argument strings —
    so the comparison matched nothing and the blocked claim was
    proposed anyway. A gate that is off says the same thing as a gate
    that let something through, which is why this is checked by what
    survives rather than by an exception.
    """
    leaky = packet(
        observations=[observation(), observation("latency_spike")],
        extra_unknowns=[
            KnownUnknown(
                id="latency_split",
                blocks_claim_types=("expansion_latency_association",),
                source="H4",
            )
        ],
    )
    response = reference_analyst(analysis(packet=leaky))
    assert [item.proposition_type for item in response.proposals] == ["geometric_infeasibility"]


def test_several_mapped_detections_do_not_kill_the_floor() -> None:
    """The same reassignment, on the pair where it raised instead.

    ``BLOCKED_BY_ARGUMENT`` holds one entry, so for every other
    detection the second pass was comparing against ``None``. The floor
    is what a real analyst is measured against; a floor that raises on
    eleven of thirteen real packets is not a comparison anybody can run.
    """
    busy = packet(
        observations=[observation("latency_spike"), observation("stuck_cluster")],
    )
    response = reference_analyst(analysis(packet=busy))
    assert [item.proposition_type for item in response.proposals] == [
        "expansion_latency_association",
        "local_minimum_entrapment",
    ]


def test_a_mechanism_check_comes_back_not_checkable_rather_than_empty() -> None:
    """The stub is honest, and the shape is one production produces too."""
    live = analysis(packet=packet(observations=[observation("latency_spike")]))
    response, host = run_round(live)
    assert response.proposals
    (result,) = host.session.results
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "checker_not_implemented"
    assert host.session.requested_tool_ids == ("latency_vs_expanded_nodes",)


def test_a_refused_request_does_not_end_the_round() -> None:
    live = analysis(
        packet=packet(observations=[observation()]),
        available_evidence=frozenset({"map_checksum"}),
    )
    response, host = run_round(live)
    assert response.proposals
    assert host.session.admitted == ()


def test_the_mock_host_serves_a_fact_query_from_the_packet() -> None:
    live = analysis()
    host = MockToolHost(live)
    host.session.declare(
        (
            HypothesisProposal(
                hypothesis_id="hyp-1",
                hypothesis_statement="a declared hypothesis",
                proposition_type="geometric_infeasibility",
                proposed_subject="costmap_inflation",
            ),
        )
    )
    result = host.call(request(live, tool_id="get_objective_decomposition"))
    assert result.execution_status == "completed"
    assert result.measurements["n_episodes"] == 30.0
    assert host.session.checker_results == ()


def test_the_packet_checksum_a_request_carries_is_the_one_the_round_computed() -> None:
    live = analysis()
    assert live.case_packet_checksum == artifact_checksum(live.packet.model_dump(mode="json"))


# --------------------------------------------------------------------------
# The data shape the card closes
# --------------------------------------------------------------------------


def test_a_request_missing_a_required_argument_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, arguments={"candidate_id": "cand_a"}))
    assert caught.value.code == "arguments_rejected"
    assert "region_id" in str(caught.value)


def test_an_argument_the_tool_does_not_take_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(
            request(
                live,
                arguments={**ARGUMENTS["gap_vs_footprint"], "confidence": "high"},
            )
        )
    assert caught.value.code == "arguments_rejected"


def test_an_argument_of_the_wrong_type_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live, arguments={"candidate_id": "cand_a", "region_id": 7}))
    assert caught.value.code == "arguments_rejected"


def test_a_boolean_is_not_an_integer_however_python_feels_about_it() -> None:
    io = ToolIO(arguments=(ArgumentSpec(name="attempt_index", kind="integer", description="x"),))
    assert io.check_arguments({"attempt_index": 3}) == ()
    assert io.check_arguments({"attempt_index": True})


def test_a_measurement_key_the_card_never_declared_is_refused() -> None:
    """Two checkers naming one quantity differently is silent data loss."""
    live = analysis()
    session = session_for(live)
    card = session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.record(
            stamped_result(
                card,
                request(live),
                execution_status="not_checkable",
                input_provenance="missing",
                failure_code="missing_footprint",
                measurements={"width": 0.68},
            )
        )
    assert caught.value.code == "measurements_rejected"


def test_a_failure_code_nobody_enumerated_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    card = session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.record(
            stamped_result(
                card,
                request(live),
                execution_status="failed",
                input_provenance="recorded",
                failure_code="it_broke",
            )
        )
    assert caught.value.code == "unknown_failure_code"


def test_the_host_may_report_its_own_failures_without_the_card_listing_them() -> None:
    live = analysis()
    session = session_for(live)
    card = session.admit(request(live))
    assert "checker_not_implemented" not in card.failure_modes
    assert "checker_not_implemented" in HOST_FAILURE_CODES
    session.record(
        stamped_result(
            card,
            request(live),
            execution_status="not_checkable",
            input_provenance="missing",
            failure_code="checker_not_implemented",
        )
    )


# --------------------------------------------------------------------------
# A request is about a hypothesis somebody proposed
# --------------------------------------------------------------------------


def test_evidence_cannot_be_gathered_for_a_hypothesis_nobody_proposed() -> None:
    live = analysis()
    session = ToolSession(live)
    with pytest.raises(ProtocolRejection) as caught:
        session.admit(request(live))
    assert caught.value.code == "unknown_hypothesis"


def test_hypotheses_may_be_declared_as_the_round_goes_on() -> None:
    """A real analyst proposes, checks, and proposes again."""
    live = analysis()
    session = session_for(live, "hyp-1")
    session.admit(request(live))
    with pytest.raises(ProtocolRejection):
        session.admit(request(live, request_id="req-002", sequence=2, hypothesis_id="hyp-2"))

    session.declare(
        (
            HypothesisProposal(
                hypothesis_id="hyp-2",
                hypothesis_statement="a later thought",
                proposition_type="geometric_infeasibility",
                proposed_subject="costmap_inflation",
            ),
        )
    )
    session.admit(request(live, request_id="req-002", sequence=2, hypothesis_id="hyp-2"))
    assert session.declared_hypotheses == ("hyp-1", "hyp-2")


# --------------------------------------------------------------------------
# The generated schemas
# --------------------------------------------------------------------------


def test_every_card_points_at_a_schema_that_exists_and_is_current() -> None:
    """A card edited without re-exporting fails here, not in production."""
    root = Path(__file__).resolve().parents[1]
    for ref, document in sorted(tool_schemas(TOOL_CATALOG).items()):
        path = root / ref
        assert path.exists(), f"{ref} is missing; run scripts/export_tool_schemas.py"
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == document, f"{ref} is stale; run scripts/export_tool_schemas.py"


def test_the_generated_schema_says_what_the_host_enforces() -> None:
    card = TOOL_CATALOG.card("gap_vs_footprint", version_of("gap_vs_footprint"))
    schema = card.io.request_schema(tool_id=card.tool_id, tool_version=card.tool_version)
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == ["candidate_id", "region_id"]
    assert card.input_schema_ref == "schemas/tools/gap_vs_footprint.request.json"


# --------------------------------------------------------------------------
# An absence must fail in the direction the comparison runs
# --------------------------------------------------------------------------


def test_an_unmeasured_counted_invariant_is_not_a_clean_sheet() -> None:
    """``at_most 0`` plus "missing means zero" reads as "no violations found".

    The harness never looked, and the gate would record a clean run.
    Which way an absence should fail is decided by the direction of the
    comparison, not by one default for every metric.
    """
    with pytest.raises(BundleRefusal, match="structural_violations"):
        CALIBRATION_TARGETS.evaluate({"precision": 0.99})


def test_an_unmeasured_rate_still_scores_zero() -> None:
    rows = {row.metric: row for row in CALIBRATION_TARGETS.evaluate({"structural_violations": 0.0})}
    assert rows["precision"].value == 0.0
    assert not rows["precision"].met
    assert rows["structural_violations"].met


def test_pass_is_a_question_you_ask_with_the_bar_in_hand() -> None:
    """``internally_passed`` is self-consistency, not the verdict."""
    lowered = tuple(
        MetricResult(
            metric=row.metric,
            value=row.value,
            threshold=0.0 if row.direction == "at_least" else row.threshold,
            direction=row.direction,
        )
        for row in CALIBRATION_TARGETS.evaluate({**CLEARING_RUN, "precision": 0.10})
    )
    forged = decision(bundle(), metrics=lowered)
    assert forged.internally_passed
    assert not forged.passes(CALIBRATION_TARGETS)


# --------------------------------------------------------------------------
# The output half of the contract
# --------------------------------------------------------------------------


def test_a_completed_check_that_reports_no_numbers_is_refused() -> None:
    """Reporting nothing is not finding nothing."""
    live = analysis()
    session = session_for(live)
    session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.record(completed_result(measurements={}))
    assert caught.value.code == "measurements_rejected"
    assert "omits required" in str(caught.value)


def test_a_check_that_did_not_run_owes_no_numbers() -> None:
    live = analysis()
    session = session_for(live)
    card = session.admit(request(live))
    session.record(
        stamped_result(
            card,
            request(live),
            execution_status="not_checkable",
            input_provenance="missing",
            failure_code="missing_footprint",
        )
    )


def test_a_navigation_tool_must_return_the_pointer_not_just_the_count() -> None:
    """``n_exemplars: 4`` says how many episodes to open, not which."""
    card = TOOL_CATALOG.card("find_exemplar_episodes", version_of("find_exemplar_episodes"))
    assert card.io.required_reference_kinds == ("episode",)

    live = analysis()
    session = session_for(live)
    ask = request(
        live,
        tool_id="find_exemplar_episodes",
        arguments={"candidate_a": "cand_a", "candidate_b": "cand_b"},
    )
    session.admit(ask)
    with pytest.raises(ProtocolRejection) as caught:
        session.record(
            stamped_result(
                card,
                ask,
                execution_status="completed",
                input_provenance="recorded",
                measurements={"n_exemplars": 4.0},
                evidence_artifact_ref="artifacts/explain/exemplars.json",
                evidence_checksum="a" * 64,
                implementation_ref="git:" + "7" * 40,
            )
        )
    assert caught.value.code == "references_rejected"


def test_a_pointer_of_a_kind_the_card_never_declared_is_refused() -> None:
    live = analysis()
    session = session_for(live)
    session.admit(request(live))
    with pytest.raises(ProtocolRejection) as caught:
        session.record(
            completed_result(references=(EvidenceReference(kind="replay_window", ref="w:1"),))
        )
    assert caught.value.code == "references_rejected"


def test_every_measurement_carries_a_unit_and_a_sentence() -> None:
    """Otherwise 0.68 is metres in one checker and centimetres in another."""
    for card in TOOL_CATALOG.cards:
        for measurement in card.io.measurements:
            assert measurement.unit
            assert measurement.description.strip()


def test_the_result_schema_states_what_a_completed_result_owes() -> None:
    card = TOOL_CATALOG.card("gap_vs_footprint", version_of("gap_vs_footprint"))
    schema = card.io.result_schema(tool_id=card.tool_id, tool_version=card.tool_version)
    measurements = schema["properties"]["measurements"]
    assert sorted(measurements["required"]) == [
        "inflation_margin_m",
        "margin_m",
        "passage_width_m",
        "required_passage_width_m",
    ]
    assert measurements["properties"]["margin_m"]["unit"] == "m"
    kinds = schema["properties"]["references"]["items"]["properties"]["kind"]["enum"]
    assert kinds == ["map_region"]


def test_an_optional_measurement_is_for_a_conditional_quantity() -> None:
    """The lower bound exists only where the map bounds one side."""
    card = TOOL_CATALOG.card("get_map_region_features", version_of("get_map_region_features"))
    optional = {
        measurement.name for measurement in card.io.measurements if not measurement.required
    }
    assert optional == {"narrowest_passage_m", "narrowest_lower_bound_m"}


# --------------------------------------------------------------------------
# A hypothesis id is bound to its content
# --------------------------------------------------------------------------


def proposal_named(hypothesis_id: str) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_id=hypothesis_id,
        hypothesis_statement="a declared hypothesis",
        proposition_type="geometric_infeasibility",
        proposed_subject="costmap_inflation",
    )


def test_declaring_the_same_proposal_twice_is_a_no_op() -> None:
    session = ToolSession(analysis())
    session.declare((proposal_named("hyp-1"),))
    session.declare((proposal_named("hyp-1"),))
    assert session.declared_hypotheses == ("hyp-1",)


def test_one_id_may_not_come_to_mean_a_different_hypothesis() -> None:
    """Otherwise evidence moves onto another claim by renaming."""
    session = ToolSession(analysis())
    session.declare((proposal_named("hyp-1"),))
    with pytest.raises(ProtocolRejection) as caught:
        session.declare(
            (
                HypothesisProposal(
                    hypothesis_id="hyp-1",
                    hypothesis_statement="something else entirely",
                    proposition_type="local_minimum_entrapment",
                    proposed_subject="local_controller",
                ),
            )
        )
    assert caught.value.code == "hypothesis_redefined"


def test_a_response_from_another_round_declares_nothing() -> None:
    session = ToolSession(analysis())
    with pytest.raises(ProtocolRejection) as caught:
        session.declare(
            AnalysisResponse(
                analysis_run_id="some-other-round",
                analyst_bundle_id=BUNDLE_ID,
                proposals=(proposal_named("hyp-1"),),
            )
        )
    assert caught.value.code == "analysis_run_mismatch"
    assert session.declared_hypotheses == ()


def test_a_response_from_another_bundle_declares_nothing() -> None:
    session = ToolSession(analysis())
    with pytest.raises(ProtocolRejection) as caught:
        session.declare(
            AnalysisResponse(
                analysis_run_id="analysis-1",
                analyst_bundle_id="some-other-bundle",
                proposals=(proposal_named("hyp-1"),),
            )
        )
    assert caught.value.code == "bundle_mismatch"


def test_the_mock_host_says_not_checkable_rather_than_inventing_zeros() -> None:
    """A stub filling required measurements with 0.0 is a stub making evidence."""
    live = analysis()
    host = MockToolHost(live)
    host.session.declare((proposal_named("hyp-1"),))
    result = host.call(
        request(
            live,
            tool_id="find_exemplar_episodes",
            arguments={"candidate_a": "cand_a", "candidate_b": "cand_b"},
        )
    )
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "tool_unavailable"


# --------------------------------------------------------------------------
# The published schema and the running host must agree
# --------------------------------------------------------------------------


def test_the_schema_requires_the_pointer_the_host_requires() -> None:
    """A schema weaker than the runtime tells an integrator a lie.

    The first version required ``measurements`` and left ``references``
    optional, so a navigation payload with no episode pointer validated
    against the published file and was refused at recording.
    """
    card = TOOL_CATALOG.card("find_exemplar_episodes", version_of("find_exemplar_episodes"))
    schema = card.io.result_schema(tool_id=card.tool_id, tool_version=card.tool_version)
    assert "references" in schema["required"]
    assert schema["properties"]["references"]["minItems"] == 1


def test_each_required_kind_gets_its_own_contains() -> None:
    """Needing an episode *and* a window is not met by two episodes."""
    io = ToolIO(
        references=(
            ReferenceSpec(kind="episode", description="which episode"),
            ReferenceSpec(kind="replay_window", description="which window"),
            ReferenceSpec(kind="map_region", required=False, description="optional region"),
        )
    )
    schema = io.result_schema(tool_id="t", tool_version="1.0.0")
    kinds = [
        entry["contains"]["properties"]["kind"]["const"]
        for entry in schema["properties"]["references"]["allOf"]
    ]
    assert kinds == ["episode", "replay_window"]


def test_a_tool_with_no_required_pointer_does_not_demand_one() -> None:
    card = TOOL_CATALOG.card(
        "get_objective_decomposition", version_of("get_objective_decomposition")
    )
    schema = card.io.result_schema(tool_id=card.tool_id, tool_version=card.tool_version)
    assert "references" not in schema["required"]
    assert "minItems" not in schema["properties"]["references"]


def test_the_generator_and_the_host_read_the_same_card() -> None:
    """Drift the file-comparison test cannot see.

    Comparing the exported file against the generator proves the file is
    current. It says nothing about whether the generator describes what
    :class:`ToolSession` actually enforces — which is the question an
    integrator is really asking of a published schema.
    """
    for card in TOOL_CATALOG.cards:
        schema = card.io.result_schema(tool_id=card.tool_id, tool_version=card.tool_version)
        measurements = schema["properties"]["measurements"]
        assert set(measurements["required"]) == set(card.io.required_measurement_keys)
        assert set(measurements["properties"]) == set(card.io.measurement_keys)

        references = schema["properties"]["references"]
        assert set(references["items"]["properties"]["kind"]["enum"]) == set(
            card.io.reference_kinds
        )
        demanded = {
            entry["contains"]["properties"]["kind"]["const"]
            for entry in references.get("allOf", [])
        }
        assert demanded == set(card.io.required_reference_kinds)
        assert ("references" in schema["required"]) == bool(card.io.required_reference_kinds)
        assert ("measurements" in schema["required"]) == bool(card.io.required_measurement_keys)


# --------------------------------------------------------------------------
# A refused declaration registers nothing
# --------------------------------------------------------------------------


def test_a_batch_that_is_refused_leaves_the_session_untouched() -> None:
    """Half a declaration is worse than none: the two sides disagree.

    The caller catches the rejection and believes it declared nothing;
    the session has already registered the proposals that came before
    the bad one.
    """
    session = ToolSession(analysis())
    session.declare((proposal_named("hyp-1"),))

    with pytest.raises(ProtocolRejection) as caught:
        session.declare(
            (
                proposal_named("hyp-2"),
                HypothesisProposal(
                    hypothesis_id="hyp-1",
                    hypothesis_statement="something else entirely",
                    proposition_type="local_minimum_entrapment",
                    proposed_subject="local_controller",
                ),
                proposal_named("hyp-3"),
            )
        )
    assert caught.value.code == "hypothesis_redefined"
    assert session.declared_hypotheses == ("hyp-1",)


def test_one_batch_cannot_contradict_itself_either() -> None:
    """Two proposals, one id, different content — refused before any write."""
    session = ToolSession(analysis())
    with pytest.raises(ProtocolRejection) as caught:
        session.declare(
            (
                proposal_named("hyp-1"),
                HypothesisProposal(
                    hypothesis_id="hyp-1",
                    hypothesis_statement="a different reading",
                    proposition_type="local_minimum_entrapment",
                    proposed_subject="local_controller",
                ),
            )
        )
    assert caught.value.code == "hypothesis_redefined"
    assert session.declared_hypotheses == ()


def test_a_batch_repeating_one_proposal_verbatim_is_still_fine() -> None:
    session = ToolSession(analysis())
    session.declare((proposal_named("hyp-1"), proposal_named("hyp-1")))
    assert session.declared_hypotheses == ("hyp-1",)
