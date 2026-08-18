"""E0 — the explanation layer's schemas say no to the right things.

These tests are mostly about what the contracts *refuse*. The layer's
whole purpose is to stop a sentence from sounding better supported than
its data, and every refusal below corresponds to a specific way that has
happened or could happen: an analyst reporting its own confidence, a
tool card whose prose promises more than its typed policy, a sidecar
that only recorded the planning attempts that succeeded.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from planbench_explanation import (
    CheckerResult,
    Claim,
    EvidencePolicy,
    EvidenceRef,
    ExplanationArtifactHeader,
    HypothesisProposal,
    ImpactRef,
    InterventionEvidence,
    InvestigationRecord,
    KnownUnknown,
    PlanningInputEvidence,
    PlanningQuery,
    PropositionOutcome,
    PropositionPolicy,
    ReplayObservation,
    SidecarViolation,
    ToolCard,
    ToolCatalog,
    ToolNotInCatalog,
    ToolPurpose,
    admit_replay_with_sidecar,
    admit_replay_without_sidecar,
    artifact_checksum,
    check_phrases,
    level_rank,
    provenance_ceiling,
    subject_ceiling,
    validate_episode_attempts,
    weakest,
)
from planbench_explanation.propositions import NotAssertableError
from planbench_explanation.provenance import MissingInputEvidence
from planbench_explanation.versioning import (
    EXPLANATION_SCHEMA_VERSION,
    PROMOTION_MATRIX_VERSION,
)
from planbench_schemas.geometry import Pose2D

REPO_ROOT = Path(__file__).resolve().parents[1]


def pose(x: float, y: float) -> Pose2D:
    return Pose2D(x=x, y=y, theta=0.0)


QUERY = PlanningQuery(start_pose=pose(0.0, 0.0), goal_pose=pose(9.0, 3.0))

#: What makes a completed checker result a *signed* one.
SIGNATURE = {
    "evidence_artifact_ref": "artifacts/explain/gap_check.json",
    "evidence_checksum": "e" * 64,
    "implementation_ref": "git:7a7c195aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
}


# --------------------------------------------------------------------------
# The analyst's object has no power to take
# --------------------------------------------------------------------------


def test_proposal_cannot_carry_a_confidence_or_a_status() -> None:
    base = {
        "hypothesis_id": "hyp-004",
        "hypothesis_statement": "B's inflation closes the B7 gap",
        "proposition_type": "geometric_infeasibility",
        "proposed_subject": "costmap_inflation",
        "supports": [{"ref": "fact:gap_width_B7", "kind": "fact"}],
    }
    HypothesisProposal(**base)

    for smuggled in ({"confidence": 0.9}, {"status": "checked"}, {"claim_level": "verified"}):
        with pytest.raises(ValidationError):
            HypothesisProposal(**base, **smuggled)


def test_proposal_cannot_carry_an_impact_number() -> None:
    with pytest.raises(ValidationError):
        HypothesisProposal(
            hypothesis_id="hyp-004",
            hypothesis_statement="B's inflation closes the B7 gap",
            proposition_type="geometric_infeasibility",
            proposed_subject="costmap_inflation",
            impact={"delta": -0.051, "method": "paired"},
        )


def test_proposal_cannot_assert_an_inference_only_type() -> None:
    with pytest.raises((NotAssertableError, ValidationError)):
        HypothesisProposal(
            hypothesis_id="hyp-009",
            hypothesis_statement="the gap explains the whole utility difference",
            proposition_type="complete_utility_attribution",
            proposed_subject="costmap_inflation",
        )


def test_claim_needs_evidence_and_a_scope() -> None:
    fields = {
        "claim_id": "claim-1",
        "level": "associated",
        "proposition_type": "local_minimum_entrapment",
        "subject": "local_controller",
        "statement": "the stop-go pattern is consistent with controller oscillation",
        "supports": [EvidenceRef(ref="obs:oscillation_B7", kind="observation")],
        "record_ref": "rec-1",
        "promotion_matrix_version": PROMOTION_MATRIX_VERSION,
    }
    Claim(scope="deployment warehouse_v1", **fields)

    with pytest.raises(ValidationError):
        Claim(scope="", **fields)
    with pytest.raises(ValidationError):
        Claim(scope="deployment warehouse_v1", **{**fields, "supports": []})


# --------------------------------------------------------------------------
# Checker results keep three questions apart
# --------------------------------------------------------------------------


def test_a_run_that_did_not_complete_has_no_verdict() -> None:
    CheckerResult(
        request_id="req-1",
        tool_id="replay_global_plan",
        tool_version="1.0.0",
        execution_status="not_checkable",
        input_provenance="missing",
    )
    with pytest.raises(ValidationError):
        CheckerResult(
            request_id="req-1",
            tool_id="replay_global_plan",
            tool_version="1.0.0",
            execution_status="not_checkable",
            input_provenance="missing",
            proposition_verdict="supported",
        )


def test_top_level_verdict_is_only_for_single_proposition_tools() -> None:
    outcomes = (
        PropositionOutcome(
            proposition_id="p1", proposition_type="geometric_infeasibility", result="supported"
        ),
        PropositionOutcome(
            proposition_id="p2", proposition_type="clearance_refusal", result="inconclusive"
        ),
    )
    with pytest.raises(ValidationError):
        CheckerResult(
            request_id="req-2",
            tool_id="gap_vs_footprint",
            tool_version="1.0.0",
            execution_status="completed",
            input_provenance="recorded",
            proposition_verdict="supported",
            supported_propositions=outcomes,
        )
    # Same result without the top-level verdict is fine.
    CheckerResult(
        request_id="req-2",
        tool_id="gap_vs_footprint",
        tool_version="1.0.0",
        execution_status="completed",
        input_provenance="recorded",
        supported_propositions=outcomes,
        **SIGNATURE,
    )


def test_a_completed_result_must_be_traceable() -> None:
    """All three fields, and the two that have a shape must have it.

    An artifact nobody can hash proves as little as a checksum over
    nothing, and neither says which build produced them. ``"x"`` in
    every field satisfies "not empty" and traces to nothing at all,
    which is the version of this rule that existed for one round.
    """
    fields = {
        "request_id": "req-4",
        "tool_id": "gap_vs_footprint",
        "tool_version": "1.0.0",
        "execution_status": "completed",
        "input_provenance": "recorded",
        "proposition_verdict": "supported",
        "supported_propositions": (
            PropositionOutcome(
                proposition_id="p1",
                proposition_type="geometric_infeasibility",
                result="supported",
            ),
        ),
    }
    CheckerResult(**fields, **SIGNATURE)  # type: ignore[arg-type]

    for dropped in SIGNATURE:
        with pytest.raises(ValidationError):
            CheckerResult(  # type: ignore[arg-type]
                **fields, **{k: v for k, v in SIGNATURE.items() if k != dropped}
            )

    for malformed in (
        {"evidence_checksum": "x"},
        {"evidence_checksum": "E" * 64},  # digests are lowercase hex
        {"implementation_ref": "x"},
        {"implementation_ref": "git:7a7c195"},  # short SHA resolves only today
        {"implementation_ref": "built by hand"},
    ):
        with pytest.raises(ValidationError):
            CheckerResult(**fields, **{**SIGNATURE, **malformed})  # type: ignore[arg-type]

    # A container digest is the other accepted form.
    CheckerResult(  # type: ignore[arg-type]
        **fields, **{**SIGNATURE, "implementation_ref": "sha256:" + "a" * 64}
    )


def test_a_completed_check_cannot_claim_missing_inputs() -> None:
    with pytest.raises(ValidationError):
        CheckerResult(
            request_id="req-3",
            tool_id="gap_vs_footprint",
            tool_version="1.0.0",
            execution_status="completed",
            input_provenance="missing",
            supported_propositions=(
                PropositionOutcome(
                    proposition_id="p1",
                    proposition_type="geometric_infeasibility",
                    result="supported",
                ),
            ),
        )


# --------------------------------------------------------------------------
# Impact refs declare which kind of impact they are
# --------------------------------------------------------------------------


def test_an_attributable_estimate_must_state_assumptions_and_uncertainty() -> None:
    ImpactRef(
        artifact_ref="artifacts/explain/impact.json",
        impact_kind="observed_contribution",
        objective="time_efficiency",
        method="paired_objective_decomposition",
    )
    with pytest.raises(ValidationError):
        ImpactRef(
            artifact_ref="artifacts/explain/impact.json",
            impact_kind="attributable_effect_estimate",
            objective="time_efficiency",
            method="detour_excision",
        )
    ImpactRef(
        artifact_ref="artifacts/explain/impact.json",
        impact_kind="attributable_effect_estimate",
        objective="time_efficiency",
        method="detour_excision",
        assumptions=("the excised segment is otherwise nominal",),
        uncertainty="bootstrap CI over 30 paired episodes",
    )


def test_knowledge_citations_pin_an_entry_version() -> None:
    EvidenceRef(ref="kb:inflation_gap_closure@2", kind="knowledge_entry")
    with pytest.raises(ValidationError):
        EvidenceRef(ref="kb:inflation_gap_closure", kind="knowledge_entry")


def test_a_known_unknown_must_block_something() -> None:
    KnownUnknown(
        id="latency_accounting_unavailable",
        blocks_claim_types=("candidate_latency_attribution", "perception_attribution"),
        source="h4_not_complete",
    )
    with pytest.raises(ValidationError):
        KnownUnknown(id="vague_worry", blocks_claim_types=(), source="a feeling")


def intervention_evidence(**overrides: object) -> InterventionEvidence:
    fields: dict[str, object] = {
        "preregistration_ref": "prereg-07",
        "axes": ("inflation_radius_m",),
        "artifact_ref": "artifacts/research/dose_response.json",
        "proposition_type": "geometric_infeasibility",
        "subject": "costmap_inflation",
        "verdict": "supported",
        "effect_direction": "removed",
        "statistical_result_ref": "artifacts/research/ddu_ci.json",
        "scope": "simulator, declared Task Neighborhood",
    }
    fields.update(overrides)
    return InterventionEvidence(**fields)  # type: ignore[arg-type]


def test_an_intervention_records_what_it_tested_and_how_it_came_out() -> None:
    """An intervention that changed nothing has not supported anything."""
    intervention_evidence(verdict="refuted", effect_direction="unchanged")
    intervention_evidence(verdict="inconclusive", effect_direction="reduced")

    with pytest.raises(ValidationError):
        intervention_evidence(verdict="supported", effect_direction="unchanged")
    with pytest.raises(ValidationError):
        intervention_evidence(verdict="supported", effect_direction="increased")
    with pytest.raises(ValidationError):  # a preregistration without a result
        intervention_evidence(statistical_result_ref="")
    with pytest.raises(ValidationError):  # no axes named
        intervention_evidence(axes=())


def test_an_intervention_belongs_to_the_research_lane() -> None:
    intervention = intervention_evidence()
    InvestigationRecord(
        record_id="rec-9",
        proposal_ref="hyp-004",
        status="checked",
        evidence_lane="research",
        intervention=intervention,
    )
    with pytest.raises(ValidationError):
        InvestigationRecord(
            record_id="rec-9",
            proposal_ref="hyp-004",
            status="checked",
            evidence_lane="evaluation",
            intervention=intervention,
        )


# --------------------------------------------------------------------------
# Tool cards: prose and typed policy cannot drift
# --------------------------------------------------------------------------


def gap_policy(**overrides: object) -> PropositionPolicy:
    fields: dict[str, object] = {
        "supported_proposition_types": ("geometric_infeasibility",),
        "forbidden_inference_types": ("complete_utility_attribution",),
        "maximum_claim_level": "mechanism_verified",
    }
    fields.update(overrides)
    return PropositionPolicy(**fields)  # type: ignore[arg-type]


GAP_PURPOSE = ToolPurpose(
    verifies={"geometric_infeasibility": "Required clearance exceeds measured passage width."},
    does_not_verify={
        "complete_utility_attribution": "This mechanism caused the whole utility difference."
    },
)


def test_every_prose_line_has_a_typed_counterpart() -> None:
    ToolCard(
        tool_id="gap_vs_footprint",
        tool_version="1.0.0",
        title="Check geometric passage feasibility",
        tool_class="mechanism_check",
        purpose=GAP_PURPOSE,
        proposition_policy=gap_policy(),
        evidence_policy=EvidencePolicy(
            allowed_input_provenance=("recorded", "verified_reconstruction")
        ),
    )

    # Prose promising something the typed policy does not support.
    with pytest.raises(ValidationError):
        ToolCard(
            tool_id="gap_vs_footprint",
            tool_version="1.0.0",
            title="Check geometric passage feasibility",
            tool_class="mechanism_check",
            purpose=ToolPurpose(
                verifies={
                    "geometric_infeasibility": "Clearance exceeds width.",
                    "local_minimum_entrapment": "And the controller got stuck.",
                },
                does_not_verify=GAP_PURPOSE.does_not_verify,
            ),
            proposition_policy=gap_policy(),
            evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
        )

    # Typed policy supporting something no sentence explains.
    with pytest.raises(ValidationError):
        ToolCard(
            tool_id="gap_vs_footprint",
            tool_version="1.0.0",
            title="Check geometric passage feasibility",
            tool_class="mechanism_check",
            purpose=GAP_PURPOSE,
            proposition_policy=gap_policy(
                supported_proposition_types=("geometric_infeasibility", "clearance_refusal")
            ),
            evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
        )


def test_a_card_cannot_both_support_and_forbid_a_proposition() -> None:
    with pytest.raises(ValidationError):
        gap_policy(forbidden_inference_types=("geometric_infeasibility",))


def test_no_card_may_license_intervention_supported() -> None:
    with pytest.raises(ValidationError):
        gap_policy(maximum_claim_level="intervention_supported")


def test_missing_is_never_an_allowed_input_provenance() -> None:
    with pytest.raises(ValidationError):
        EvidencePolicy(allowed_input_provenance=("recorded", "missing"))


def test_navigation_tools_promote_nothing_and_research_tools_never_run() -> None:
    with pytest.raises(ValidationError):
        ToolCard(
            tool_id="find_exemplar_episodes",
            tool_version="1.0.0",
            title="Find exemplar episodes",
            tool_class="evidence_navigation",
            purpose=GAP_PURPOSE,
            proposition_policy=gap_policy(),
            evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
        )

    with pytest.raises(ValidationError):
        ToolCard(
            tool_id="build_parameter_intervention_spec",
            tool_version="1.0.0",
            title="Draft a parameter intervention",
            tool_class="research_proposal",
            lane="research",
            execution_authorized=True,
            proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
            evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
        )

    ToolCard(
        tool_id="build_parameter_intervention_spec",
        tool_version="1.0.0",
        title="Draft a parameter intervention",
        tool_class="research_proposal",
        lane="research",
        execution_authorized=False,
        proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
        evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
    )


def test_catalog_refuses_duplicates_and_unknown_lookups() -> None:
    card = ToolCard(
        tool_id="gap_vs_footprint",
        tool_version="1.0.0",
        title="Check geometric passage feasibility",
        tool_class="mechanism_check",
        purpose=GAP_PURPOSE,
        proposition_policy=gap_policy(),
        evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
    )
    with pytest.raises(ValidationError):
        ToolCatalog(catalog_version="1.0.0", cards=(card, card))

    catalog = ToolCatalog(catalog_version="1.0.0", cards=(card,))
    assert catalog.card("gap_vs_footprint", "1.0.0") is card
    with pytest.raises(ToolNotInCatalog):
        catalog.card("gap_vs_footprint", "2.0.0")


# --------------------------------------------------------------------------
# Ladder, ceilings, wording
# --------------------------------------------------------------------------


def test_levels_are_ordered_and_ceilings_compose_by_minimum() -> None:
    assert level_rank("observed") < level_rank("associated") < level_rank("mechanism_verified")
    assert weakest("mechanism_verified", "associated") == "associated"
    assert weakest("intervention_supported", "observed", "associated") == "observed"


def test_reconstructed_inputs_cap_at_associated_and_missing_ones_support_nothing() -> None:
    assert provenance_ceiling("reconstructed") == "associated"
    assert provenance_ceiling("recorded") == "intervention_supported"
    with pytest.raises(MissingInputEvidence):
        provenance_ceiling("missing")


def test_perception_and_transport_are_capped_until_h4() -> None:
    assert subject_ceiling("perception_provider") == "observed"
    assert subject_ceiling("runtime_transport") == "observed"
    assert subject_ceiling("global_planner") == "intervention_supported"
    assert (
        subject_ceiling("perception_provider", h4_accounting_complete=True)
        == "intervention_supported"
    )


def test_causal_wording_is_refused_below_the_top_rung() -> None:
    sentence = "the detour occurred because of the closed gap"
    assert check_phrases(sentence, "associated") == ("because of",)
    assert check_phrases(sentence, "mechanism_verified") == ("because of",)
    assert check_phrases(sentence, "intervention_supported") == ()
    # The pattern matches words, not substrings.
    assert check_phrases("the robot recaused nothing here", "observed") == ()
    assert check_phrases("the gap width was measured at 0.68 m", "observed") == ()


# --------------------------------------------------------------------------
# Sidecar: every attempt, including the failures
# --------------------------------------------------------------------------


def sidecar(attempt: int = 1, **overrides: object) -> PlanningInputEvidence:
    fields: dict[str, object] = {
        "episode_context_id": "ctx017",
        "candidate_id": "cand0001",
        "planning_attempt": attempt,
        "simulation_tick": 148,
        "query": QUERY,
        "costmap_checksum": "cm-abc",
        "planner_fingerprint": "astar@w1.0",
        "execution_environment_ref": "git:7a7c195aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "outcome": "no_path",
        "failure_code": "no_global_path",
    }
    fields.update(overrides)
    return PlanningInputEvidence(**fields)  # type: ignore[arg-type]


def test_outcome_and_checksum_and_failure_code_must_agree() -> None:
    sidecar()
    sidecar(outcome="path", output_plan_checksum="plan-1", failure_code=None)

    with pytest.raises(ValidationError):  # path without a plan checksum
        sidecar(outcome="path", failure_code=None)
    with pytest.raises(ValidationError):  # no_path with a plan checksum
        sidecar(output_plan_checksum="plan-1")
    with pytest.raises(ValidationError):  # no_path without a reason
        sidecar(failure_code=None)
    with pytest.raises(ValidationError):  # an environment nobody can resolve
        sidecar(execution_environment_ref="git:7a7c195")


def test_a_missing_attempt_is_refused_rather_than_averaged_over() -> None:
    validate_episode_attempts([sidecar(1), sidecar(2), sidecar(3)], expected_attempts=3)

    with pytest.raises(SidecarViolation):  # hole in the middle
        validate_episode_attempts([sidecar(1), sidecar(3)], expected_attempts=3)
    with pytest.raises(SidecarViolation):
        validate_episode_attempts([sidecar(1), sidecar(1)], expected_attempts=2)
    with pytest.raises(SidecarViolation):
        validate_episode_attempts(
            [sidecar(1), sidecar(2, episode_context_id="ctx018")], expected_attempts=2
        )
    with pytest.raises(SidecarViolation):
        validate_episode_attempts([], expected_attempts=1)


def test_a_truncated_tail_is_caught_by_the_runners_own_count() -> None:
    """The shape contiguity alone cannot see.

    ``[1]`` is a perfectly contiguous list, and for an episode that
    replanned twice it is a writer that stopped early — which is
    precisely the case the sidecar exists to record.
    """
    with pytest.raises(SidecarViolation) as excinfo:
        validate_episode_attempts([sidecar(1)], expected_attempts=3)
    assert "missing [2, 3]" in str(excinfo.value)

    with pytest.raises(SidecarViolation):  # more records than the runner counted
        validate_episode_attempts([sidecar(1), sidecar(2)], expected_attempts=1)
    with pytest.raises(SidecarViolation):  # counter never read
        validate_episode_attempts([sidecar(1)], expected_attempts=0)


def test_a_replay_over_recorded_inputs_can_reach_mechanism_verified() -> None:
    recorded = sidecar(outcome="path", output_plan_checksum="plan-1", failure_code=None)
    replayed = ReplayObservation(
        costmap_checksum="cm-abc",
        query=QUERY,
        planner_fingerprint="astar@w1.0",
        execution_environment_ref="git:7a7c195aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        outcome="path",
        output_plan_checksum="plan-1",
    )

    loaded = admit_replay_with_sidecar(recorded, replayed, inputs_loaded_from_record=True)
    assert loaded.input_provenance == "recorded"
    assert loaded.maximum_supported_level == "mechanism_verified"

    rebuilt = admit_replay_with_sidecar(recorded, replayed, inputs_loaded_from_record=False)
    assert rebuilt.input_provenance == "verified_reconstruction"
    assert rebuilt.maximum_supported_level == "mechanism_verified"

    drifted = admit_replay_with_sidecar(
        recorded,
        replayed.model_copy(update={"execution_environment_ref": "git:" + "deadbee" + "b" * 33}),
        inputs_loaded_from_record=False,
    )
    assert drifted.execution_status == "not_checkable"
    assert drifted.maximum_supported_level is None
    assert "mismatch:execution_environment_ref" in drifted.reasons


def test_a_replay_must_refuse_for_the_same_reason_the_run_did() -> None:
    """``no_global_path`` and ``planner_timeout`` are both ``no_path``.

    They are different mechanisms, and the mechanism is the subject of
    the claim, so a replay that reproduces the outcome with another
    reason has not reproduced anything.
    """
    recorded = sidecar()  # no_path / no_global_path
    replayed = ReplayObservation(
        costmap_checksum="cm-abc",
        query=QUERY,
        planner_fingerprint="astar@w1.0",
        execution_environment_ref="git:7a7c195aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        outcome="no_path",
        failure_code="planner_timeout",
    )
    admission = admit_replay_with_sidecar(recorded, replayed, inputs_loaded_from_record=True)
    assert admission.execution_status == "not_checkable"
    assert "mismatch:failure_code" in admission.reasons

    same_reason = admit_replay_with_sidecar(
        recorded,
        replayed.model_copy(update={"failure_code": "no_global_path"}),
        inputs_loaded_from_record=True,
    )
    assert same_reason.execution_status == "completed"


def test_without_the_sidecar_a_matching_plan_is_still_only_associated() -> None:
    replayed = ReplayObservation(
        costmap_checksum="cm-rebuilt",
        query=QUERY,
        planner_fingerprint="astar@w1.0",
        execution_environment_ref="git:7a7c195aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        outcome="path",
        output_plan_checksum="plan-1",
    )

    matched = admit_replay_without_sidecar(
        replayed, recorded_output_plan_checksum="plan-1", plans_recorded=True
    )
    assert matched.execution_status == "completed"
    assert matched.input_provenance == "reconstructed"
    assert matched.maximum_supported_level == "associated"

    refuted = admit_replay_without_sidecar(
        replayed, recorded_output_plan_checksum="plan-other", plans_recorded=True
    )
    assert refuted.execution_status == "not_checkable"
    assert "reconstruction_refuted:output_plan_differs" in refuted.reasons

    unrecorded = admit_replay_without_sidecar(
        replayed, recorded_output_plan_checksum=None, plans_recorded=False
    )
    assert unrecorded.execution_status == "not_checkable"
    assert unrecorded.reasons == ("plans_not_recorded",)


# --------------------------------------------------------------------------
# Artifact versioning and the one-way reference to the manifest
# --------------------------------------------------------------------------


def header() -> ExplanationArtifactHeader:
    return ExplanationArtifactHeader.for_current_code(
        source_manifest_ref="runs/2026-08-18/abc123/manifest.json",
        source_manifest_checksum="a" * 64,
        detector_version="0.1.0",
        knowledge_base_version="kb-v1",
        tool_catalog_version="1.0.0",
    )


def test_header_stamps_the_versions_the_code_owns() -> None:
    stamped = header()
    assert stamped.explanation_schema_version == EXPLANATION_SCHEMA_VERSION
    assert stamped.promotion_matrix_version == PROMOTION_MATRIX_VERSION


def test_header_refuses_a_checksum_that_is_not_one() -> None:
    with pytest.raises(ValidationError):
        ExplanationArtifactHeader.model_validate(
            header().model_dump() | {"source_manifest_checksum": "nope"}
        )


def test_the_reference_to_the_manifest_is_one_way() -> None:
    """No manifest field is copied into an explanation artifact.

    Two places recording ``anchor_config_version`` is two places to
    disagree, and the explanation is the one nobody would think to
    check.
    """
    schema = json.loads(
        (REPO_ROOT / "contracts" / "schemas" / "manifest.schema.json").read_text(encoding="utf-8")
    )
    manifest_fields = set(schema.get("properties", {}))
    header_fields = set(ExplanationArtifactHeader.model_fields)
    assert manifest_fields & header_fields == set()


def test_artifact_checksum_is_stable_and_sensitive() -> None:
    payload = {"claims": [{"id": "c1", "level": "associated"}]}
    assert artifact_checksum(payload) == artifact_checksum(
        {"claims": [{"level": "associated", "id": "c1"}]}
    )
    assert artifact_checksum(payload) != artifact_checksum({"claims": []})
