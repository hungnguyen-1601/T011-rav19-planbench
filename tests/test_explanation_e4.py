"""E4 — the packet, the ledger, the templates and the five panels.

What these guard, in one line each: an analyst may not be handed
evidence it cannot check; a ledger may not lose the reason a claim was
refused; a template may not say more than its rung; and a panel may not
draw a decomposition of a difference that was never computed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_decision.objectives import PREFERENCE_PROFILES
from planbench_explanation.case_packet import (
    STANDING_UNKNOWNS,
    CasePacket,
    CasePacketRefusal,
    DecisionFacts,
    RobotFacts,
    TaskFacts,
    build_case_packet,
)
from planbench_explanation.contrast import CandidateComponents
from planbench_explanation.detectors import Observation
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.ledger import (
    CheckerResult,
    Claim,
    EvidenceRef,
    HypothesisProposal,
    ImpactRef,
    InvestigationRecord,
    KnownUnknown,
    PropositionOutcome,
)
from planbench_explanation.ledger_store import LedgerRefusal, build_ledger
from planbench_explanation.panel import (
    RUN_OUTCOMES,
    PanelPlan,
    PanelRefusal,
    outcome_of,
    panel_for,
    plan_for,
)
from planbench_explanation.render import RenderRefusal, render_claim, render_no_claim
from planbench_explanation.tools import (
    EvidencePolicy,
    PropositionPolicy,
    ToolCard,
    ToolCatalog,
    ToolPurpose,
)
from planbench_explanation.versioning import (
    PROMOTION_MATRIX_VERSION,
    ExplanationArtifactHeader,
)
from planbench_explanation.waterfall import (
    ObjectiveLevels,
    UtilityDrillDown,
    Waterfall,
    WaterfallBar,
    WaterfallProfile,
)

SCOPE = "deployment warehouse_crossing_v1"
SIGNATURE = {
    "evidence_artifact_ref": "artifacts/explain/check.json",
    "evidence_checksum": "e" * 64,
    "implementation_ref": "git:" + "7a7c195" + "a" * 33,
}


def header() -> ExplanationArtifactHeader:
    return ExplanationArtifactHeader.for_current_code(
        source_manifest_ref="runs/2026-08-19/abc/manifest.json",
        source_manifest_checksum="a" * 64,
        detector_version="0.1.0",
        knowledge_base_version=KNOWLEDGE_BASE_VERSION,
        tool_catalog_version="1.0.0",
    )


def waterfall(candidate_a: str = "cand_a", candidate_b: str = "cand_b") -> Waterfall:
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
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        profile=WaterfallProfile(kind="canonical", base_profile="kho_ban_dem", weights=weights),
        n_episodes=30,
        delta_utility_mean=0.0,
        delta_utility_median=0.0,
        total_ci95=(-0.02, 0.02),
        bars=bars,
        drill_down=UtilityDrillDown(
            candidate_a=candidate_a,
            candidate_b=candidate_b,
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
        "run_id": "run_017",
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


# --------------------------------------------------------------------------
# The packet
# --------------------------------------------------------------------------


def test_a_packet_always_carries_the_gaps_the_platform_has() -> None:
    """An empty list would claim the platform knows everything.

    The H4 accounting gaps alone make that untrue today, which is why
    they are data rather than something each caller remembers.
    """
    built = packet()

    assert {item.id for item in STANDING_UNKNOWNS} <= {item.id for item in built.known_unknowns}
    assert "candidate_latency_attribution" in built.blocked_claim_types


def test_an_extra_gap_adds_to_the_standing_ones_rather_than_replacing_them() -> None:
    built = packet(
        extra_unknowns=[
            KnownUnknown(
                id="tracker_config_unrecorded",
                blocks_claim_types=("perception_attribution",),
                source="deployment_did_not_declare_it",
            )
        ]
    )

    assert len(built.known_unknowns) == len(STANDING_UNKNOWNS) + 1


def test_a_repeated_gap_id_is_refused() -> None:
    with pytest.raises(CasePacketRefusal, match="already one of the standing gaps"):
        packet(
            extra_unknowns=[
                KnownUnknown(
                    id="latency_accounting_unavailable",
                    blocks_claim_types=("perception_attribution",),
                    source="somewhere_else",
                )
            ]
        )


def test_a_packet_cannot_be_built_without_the_gaps_at_all() -> None:
    with pytest.raises((CasePacketRefusal, ValidationError)):
        CasePacket(
            header=header(),
            run_id="run",
            task=TaskFacts(task_profile_id="p", robot=RobotFacts(radius_m=0.26)),
            candidates=(stack("cand_a"), stack("cand_b")),
            decision=DecisionFacts(status="CLEAR_RECOMMENDATION", waterfall=waterfall()),
            known_unknowns=(),
            evidence_class="production",
        )


def test_the_packet_must_describe_the_candidates_it_compares() -> None:
    # Raised inside a validator, so it reaches the caller wrapped — the
    # same way ``StatisticsRefusal`` does in the decision layer.
    with pytest.raises(ValidationError, match="cannot see"):
        packet(candidates=[stack("someone"), stack("else", "rrtstar")])


def test_an_observation_about_a_stranger_is_refused() -> None:
    stranger = Observation(type="detour", candidate_id="ghost", episodes_seen=1, episodes_total=30)
    with pytest.raises(ValidationError, match="not in this packet"):
        packet(observations=[stranger])


def test_a_packet_whose_knowledge_base_moved_is_refused() -> None:
    """Citations that resolve against another base cannot be re-read."""
    stale = header().model_copy(update={"knowledge_base_version": "v0.9.0"})
    with pytest.raises(CasePacketRefusal, match="knowledge base"):
        packet(header=stale)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


def claim(level: str = "observed", **overrides) -> Claim:  # type: ignore[no-untyped-def]
    fields = {
        "claim_id": "c1",
        "level": level,
        "proposition_type": "geometric_infeasibility",
        "subject": "costmap_inflation",
        "statement": "the B7 passage is 0.68 m across",
        "scope": SCOPE,
        "supports": (EvidenceRef(ref="fact:gap_width", kind="fact"),),
        "record_ref": "rec-1",
        "promotion_matrix_version": PROMOTION_MATRIX_VERSION,
    }
    fields.update(overrides)
    return Claim(**fields)  # type: ignore[arg-type]


def test_each_rung_gets_the_verb_its_evidence_licenses() -> None:
    assert render_claim(claim("observed")).startswith("Measured:")
    assert render_claim(claim("associated")).startswith("Consistent with costmap inflation:")
    assert render_claim(claim("mechanism_verified")).startswith("Verified for costmap inflation:")

    caused = render_claim(claim("intervention_supported"))
    assert caused.startswith("Caused by costmap inflation:")
    # The top rung always states its bounds.
    assert SCOPE in caused


def test_a_statement_that_overreaches_its_rung_is_refused_at_render_time() -> None:
    """The check that survives somebody editing a template.

    ``associated`` may not say "because of", however the sentence got
    that far.
    """
    with pytest.raises(RenderRefusal, match="does not license"):
        render_claim(claim("associated", statement="the detour happened because of the gap"))


def test_the_two_impact_kinds_do_not_read_alike() -> None:
    observed = render_claim(
        claim(
            "mechanism_verified",
            impact_ref=ImpactRef(
                artifact_ref="artifacts/impact.json",
                impact_kind="observed_contribution",
                objective="time_efficiency",
                method="paired_objective_decomposition",
            ),
        )
    )
    estimated = render_claim(
        claim(
            "mechanism_verified",
            qualifiers=("estimated",),
            impact_ref=ImpactRef(
                artifact_ref="artifacts/impact.json",
                impact_kind="attributable_effect_estimate",
                objective="time_efficiency",
                method="detour_excision",
                assumptions=("the excised segment is otherwise nominal",),
                uncertainty="paired bootstrap CI",
            ),
        )
    )

    assert "not established" in observed
    assert "Estimated to account for" in estimated
    assert "estimated" in estimated  # the qualifier travels too


def test_a_profile_weighted_impact_names_the_profile_on_the_same_line() -> None:
    """Otherwise a preference reads as a measurement — and two different
    preferences read as the same one."""
    sentence = render_claim(
        claim(
            "associated",
            impact_ref=ImpactRef(
                artifact_ref="artifacts/impact.json",
                impact_kind="observed_contribution",
                objective="time_efficiency",
                method="paired_objective_decomposition",
                profile_weighted=True,
                profile_ref="kho_ban_dem",
            ),
        )
    )
    # Named, not merely flagged: two runs under different preferences
    # rendered identically while this was a bare boolean.
    assert "kho_ban_dem" in sentence


def test_no_number_appears_that_the_ledger_does_not_hold() -> None:
    """``ImpactRef`` carries no float, so no sentence may quote one."""
    sentence = render_claim(
        claim(
            "mechanism_verified",
            impact_ref=ImpactRef(
                artifact_ref="artifacts/impact.json",
                impact_kind="attributable_effect_estimate",
                objective="time_efficiency",
                method="detour_excision",
                assumptions=("a",),
                uncertainty="b",
            ),
        )
    )
    assert "artifacts/impact.json" in sentence


def test_an_empty_panel_is_given_words() -> None:
    assert "Not enough evidence" in render_no_claim()
    assert "refuted_by:gap_vs_footprint@1.0.0" in render_no_claim(
        "refuted_by:gap_vs_footprint@1.0.0"
    )


# --------------------------------------------------------------------------
# The ledger
# --------------------------------------------------------------------------

GAP_CARD = ToolCard(
    tool_id="gap_vs_footprint",
    tool_version="1.0.0",
    title="Check geometric passage feasibility",
    tool_class="mechanism_check",
    purpose=ToolPurpose(
        verifies={"geometric_infeasibility": "Required clearance exceeds passage width."},
        does_not_verify={"complete_utility_attribution": "It produced the whole gap."},
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("geometric_infeasibility",),
        forbidden_inference_types=("complete_utility_attribution",),
        maximum_claim_level="mechanism_verified",
    ),
    evidence_policy=EvidencePolicy(allowed_input_provenance=("recorded",)),
)
CATALOG = ToolCatalog(catalog_version="1.0.0", cards=(GAP_CARD,))


def proposal(proposition: str = "geometric_infeasibility") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_id="hyp-1",
        hypothesis_statement="inflation closes the gap",
        proposition_type=proposition,  # type: ignore[arg-type]
        proposed_subject="costmap_inflation",
        supports=(
            EvidenceRef(ref="fact:gap_width", kind="fact"),
            EvidenceRef(ref="obs:detour", kind="observation"),
        ),
    )


def record(**overrides) -> InvestigationRecord:  # type: ignore[no-untyped-def]
    fields = {
        "record_id": "rec-1",
        "proposal_ref": "hyp-1",
        "status": "checked",
        "checker_results": (
            CheckerResult(
                request_id="req-1",
                tool_id="gap_vs_footprint",
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
            ),
        ),
        "impact_ref": ImpactRef(
            artifact_ref="artifacts/impact.json",
            impact_kind="observed_contribution",
            objective="time_efficiency",
            method="paired_objective_decomposition",
        ),
    }
    fields.update(overrides)
    return InvestigationRecord(**fields)  # type: ignore[arg-type]


def test_the_ledger_keeps_what_was_refused_and_why() -> None:
    """Blank and "three checks refuted it" look identical on a panel."""
    ledger = build_ledger(
        packet(),
        [
            (
                proposal(),
                record(status="check_failed", checker_results=()),
                "the B7 passage is consistent with a closed gap",
            )
        ],
        catalog=CATALOG,
        scope=SCOPE,
    )

    assert ledger.claims == ()
    (entry,) = ledger.refused
    assert entry.reasons == ("record_status:check_failed",)
    assert "Not enough evidence" in entry.sentence


def test_a_promoted_claim_arrives_rendered() -> None:
    ledger = build_ledger(
        packet(),
        [(proposal(), record(), "the B7 passage is narrower than the required clearance")],
        catalog=CATALOG,
        scope=SCOPE,
    )

    (claim_made,) = ledger.claims
    assert claim_made.level == "mechanism_verified"
    assert ledger.entries[0].sentence.startswith("Verified for costmap inflation:")


def test_the_packets_gaps_are_enforced_with_no_way_to_opt_out() -> None:
    """A caller able to drop the H4 gap could promote what H4 cannot."""
    ledger = build_ledger(
        packet(),
        [
            (
                proposal("candidate_latency_attribution"),
                record(),
                "the candidate's compute co-occurs with the latency",
            )
        ],
        catalog=CATALOG,
        scope=SCOPE,
    )

    assert ledger.claims == ()
    assert ledger.entries[0].reasons == ("blocked_by_known_unknown:latency_accounting_unavailable",)


def test_the_ledger_names_the_packet_it_answered() -> None:
    built = packet()
    ledger = build_ledger(built, [], catalog=CATALOG, scope=SCOPE)

    assert len(ledger.case_packet_checksum) == 64
    # A different packet is a different question.
    other = build_ledger(packet(evidence_class="reference"), [], catalog=CATALOG, scope=SCOPE)
    assert other.case_packet_checksum != ledger.case_packet_checksum


def test_two_adjudications_of_one_hypothesis_are_refused() -> None:
    with pytest.raises((LedgerRefusal, ValidationError)):
        build_ledger(
            packet(),
            [
                (proposal(), record(), "the passage is narrow"),
                (proposal(), record(), "the passage is narrow"),
            ],
            catalog=CATALOG,
            scope=SCOPE,
        )


# --------------------------------------------------------------------------
# The five panels
# --------------------------------------------------------------------------


def test_the_three_no_card_outcomes_show_no_comparison() -> None:
    """No ΔU exists, so there is nothing to decompose or claim about."""
    for outcome in ("no_survivors", "gate_only"):
        plan = plan_for(outcome, has_comparison=False)  # type: ignore[arg-type]
        assert not plan.show_waterfall
        assert not plan.show_claims
        assert not plan.show_exemplars
        assert plan.show_gate_table


def test_a_panel_that_would_draw_a_comparison_that_never_ran_is_refused() -> None:
    with pytest.raises((PanelRefusal, ValidationError), match="never asked"):
        PanelPlan(
            outcome="gate_only",
            show_waterfall=True,
            show_claims=False,
            show_exemplars=False,
            show_gate_table=True,
            headline_key="explain.headline.gateOnly",
        )


def test_near_equivalent_says_the_tie_break_decided_it() -> None:
    """The interval covers zero; the ranking did not decide this."""
    plan = plan_for("near_equivalent", has_comparison=True)
    assert "explain.caveat.insideTheNoise" in plan.caveat_keys
    assert "explain.caveat.tieBreak" in plan.caveat_keys


def test_an_interrupted_run_keeps_its_evidence_and_its_caveat() -> None:
    plan = plan_for("interrupted", has_comparison=True)
    assert plan.show_waterfall
    assert "explain.caveat.fewerEpisodes" in plan.caveat_keys


def test_a_run_interrupted_before_ranking_has_no_comparison_to_show() -> None:
    """The composition bug: both halves right, the pair wrong.

    ``outcome_of`` called it interrupted, the interrupted plan switched
    the waterfall on, and nothing checked that this run ever produced a
    ΔU to decompose.
    """
    plan = panel_for(ranked=False, status=None, interrupted=True, gate_only=False)

    assert plan.outcome == "interrupted"
    assert not plan.show_waterfall
    assert not plan.show_claims
    assert not plan.show_exemplars
    assert "explain.caveat.noComparisonYet" in plan.caveat_keys


def test_a_ranked_outcome_cannot_claim_to_have_no_comparison() -> None:
    with pytest.raises(PanelRefusal, match="contradicts"):
        plan_for("clear", has_comparison=False)
    with pytest.raises(PanelRefusal, match="never has a paired comparison"):
        plan_for("gate_only", has_comparison=True)


def test_every_outcome_has_a_plan_and_a_headline() -> None:
    for outcome in RUN_OUTCOMES:
        for has_comparison in (True, False):
            try:
                plan = plan_for(outcome, has_comparison=has_comparison)
            except PanelRefusal:
                continue
            assert plan.headline_key


def test_not_finishing_is_the_fact_that_leads() -> None:
    """A run that stopped early may also have had nobody survive, and
    "we did not finish" is what makes the second uninterpretable."""
    assert outcome_of(ranked=False, status=None, interrupted=True, gate_only=True) == "interrupted"
    assert outcome_of(ranked=False, status=None, interrupted=False, gate_only=True) == "gate_only"
    assert (
        outcome_of(ranked=False, status=None, interrupted=False, gate_only=False) == "no_survivors"
    )
    assert (
        outcome_of(ranked=True, status="NEAR_EQUIVALENT", interrupted=False, gate_only=False)
        == "near_equivalent"
    )
    assert (
        outcome_of(ranked=True, status="CLEAR_RECOMMENDATION", interrupted=False, gate_only=False)
        == "clear"
    )


# --------------------------------------------------------------------------
# What a hand-edited artifact must not get away with
# --------------------------------------------------------------------------


def test_a_claim_stapled_to_another_investigation_is_refused() -> None:
    """ "The UI only renders gated claims" is worth the checks on the file."""
    ledger = build_ledger(
        packet(),
        [(proposal(), record(), "the B7 passage is narrower than the required clearance")],
        catalog=CATALOG,
        scope=SCOPE,
    )
    payload = ledger.model_dump()
    payload["entries"][0]["claim"]["record_ref"] = "rec-somewhere-else"

    with pytest.raises(ValidationError, match="another investigation"):
        ledger.__class__.model_validate(payload)


def test_a_sentence_that_is_not_what_the_claim_renders_to_is_refused() -> None:
    """A stored sentence free to differ is free to say more."""
    ledger = build_ledger(
        packet(),
        [(proposal(), record(), "the B7 passage is narrower than the required clearance")],
        catalog=CATALOG,
        scope=SCOPE,
    )
    payload = ledger.model_dump()
    payload["entries"][0]["sentence"] = "Caused by costmap inflation: the robot got stuck."

    with pytest.raises(ValidationError, match="not what this claim renders to"):
        ledger.__class__.model_validate(payload)


def test_a_claim_about_another_proposition_or_subject_is_refused() -> None:
    ledger = build_ledger(
        packet(),
        [(proposal(), record(), "the B7 passage is narrower than the required clearance")],
        catalog=CATALOG,
        scope=SCOPE,
    )
    for field, value, message in (
        ("proposition_type", "local_minimum_entrapment", "while the proposal asked"),
        ("subject", "global_planner", "while the proposal proposed"),
    ):
        payload = ledger.model_dump()
        payload["entries"][0]["claim"][field] = value
        with pytest.raises(ValidationError, match=message):
            ledger.__class__.model_validate(payload)


def test_the_h4_ceiling_is_not_something_a_caller_can_lift() -> None:
    """It used to be a keyword on ``build_ledger``.

    That put "has the accounting landed?" in the hands of whoever called
    it — including the party whose candidate is being judged.
    """
    import inspect

    from planbench_explanation.ledger_store import build_ledger as builder
    from planbench_explanation.subjects import H4_ACCOUNTING_COMPLETE

    assert "h4_accounting_complete" not in inspect.signature(builder).parameters
    assert H4_ACCOUNTING_COMPLETE is False


def test_a_lattice_reading_from_another_run_cannot_enter_the_packet() -> None:
    from planbench_explanation.contrast import ContrastFinding

    stranger = ContrastFinding(
        detection_type="detour",
        verdict="rules_out_component_specific_attribution",
        subject="global_planner",
        pairs=(("cand_a", "someone_elses_candidate"),),
        reason="from a different run entirely",
    )

    with pytest.raises(ValidationError, match="not in this packet"):
        packet(lattice=[stranger])


def test_exemplars_for_the_same_pair_the_other_way_round_are_refused() -> None:
    """``strongest_for_winner`` is defined against a direction.

    Compared as a set, the reversed pair passed — and the same four
    episodes then sat under two swapped labels.
    """
    from planbench_explanation.exemplars import Exemplar, ExemplarSet

    reversed_set = ExemplarSet(
        candidate_a="cand_b",
        candidate_b="cand_a",
        n_episodes=30,
        exemplars=tuple(
            Exemplar(role=role, episode_context_id="ep00", delta_utility=0.0, criterion=0.0)
            for role in (
                "typical",
                "strongest_for_winner",
                "strongest_for_runnerup",
                "safety_critical",
            )
        ),
    )

    with pytest.raises(ValidationError, match="the other way round"):
        packet(representative_episodes=reversed_set)


def test_a_profile_weighted_impact_without_a_profile_is_refused() -> None:
    with pytest.raises(ValidationError, match="must name the profile"):
        ImpactRef(
            artifact_ref="artifacts/impact.json",
            impact_kind="observed_contribution",
            objective="time_efficiency",
            method="paired_objective_decomposition",
            profile_weighted=True,
        )

    with pytest.raises(ValidationError, match="not marked"):
        ImpactRef(
            artifact_ref="artifacts/impact.json",
            impact_kind="observed_contribution",
            objective="time_efficiency",
            method="paired_objective_decomposition",
            profile_ref="kho_ban_dem",
        )


# --------------------------------------------------------------------------
# Parsing is not verification
# --------------------------------------------------------------------------


def promoted_ledger():  # type: ignore[no-untyped-def]
    return packet(), build_ledger(
        packet(),
        [(proposal(), record(), "the B7 passage is narrower than the required clearance")],
        catalog=CATALOG,
        scope=SCOPE,
    )


def test_a_consistently_forged_claim_passes_parsing_and_fails_verification() -> None:
    """The attack the schema cannot see.

    Raise the level, re-render the sentence so it matches, leave the
    matrix version alone: every cross-link check passes, because they
    only prove two fields were edited *consistently*. Whether the record
    earned that level depends on the tool catalog and the packet, and
    neither is in the file.
    """
    from planbench_explanation.ledger_store import (
        ClaimLedger,
        LedgerVerificationFailure,
        verify_ledger,
    )
    from planbench_explanation.render import render_claim

    built_packet, ledger = promoted_ledger()
    assert ledger.claims[0].level == "mechanism_verified"

    forged = ledger.claims[0].model_copy(update={"level": "intervention_supported"})
    payload = ledger.model_dump()
    payload["entries"][0]["claim"] = forged.model_dump()
    payload["entries"][0]["sentence"] = render_claim(forged)

    # Reads back cleanly...
    parsed = ClaimLedger.model_validate(payload)
    assert parsed.claims[0].level == "intervention_supported"

    # ...and does not survive being re-derived.
    with pytest.raises(LedgerVerificationFailure, match=r"entries\.0\.claim\.level"):
        verify_ledger(parsed, built_packet, catalog=CATALOG, scope=SCOPE)


def test_verification_returns_the_rebuilt_ledger_so_the_stale_one_is_not_used() -> None:
    from planbench_explanation.ledger_store import verify_ledger

    built_packet, ledger = promoted_ledger()
    verified = verify_ledger(ledger, built_packet, catalog=CATALOG, scope=SCOPE)

    assert verified.model_dump() == ledger.model_dump()
    assert verified is not ledger


def test_a_ledger_verified_against_another_packet_is_refused() -> None:
    """The packet is half the input; the wrong one is a different question."""
    from planbench_explanation.ledger_store import LedgerVerificationFailure, verify_ledger

    _, ledger = promoted_ledger()

    with pytest.raises(LedgerVerificationFailure, match="different packet"):
        verify_ledger(ledger, packet(evidence_class="reference"), catalog=CATALOG, scope=SCOPE)


def test_a_forged_refusal_reason_is_caught_too() -> None:
    from planbench_explanation.ledger_store import (
        ClaimLedger,
        LedgerVerificationFailure,
        verify_ledger,
    )
    from planbench_explanation.render import render_no_claim

    built_packet = packet()
    ledger = build_ledger(
        built_packet,
        [(proposal(), record(status="check_failed", checker_results=()), "irrelevant")],
        catalog=CATALOG,
        scope=SCOPE,
    )
    payload = ledger.model_dump()
    payload["entries"][0]["reasons"] = ["no_applicable_check:resting_at_associated"]
    payload["entries"][0]["sentence"] = render_no_claim("no_applicable_check:resting_at_associated")

    with pytest.raises(LedgerVerificationFailure, match=r"entries\.0\.reasons"):
        verify_ledger(
            ClaimLedger.model_validate(payload), built_packet, catalog=CATALOG, scope=SCOPE
        )


def test_the_verifier_does_not_take_its_question_from_the_answer() -> None:
    """The circularity the first verifier had.

    It re-promoted using ``claim.statement``. So swapping the claim for a
    conclusion about a *different passage* and re-rendering the sentence
    meant the matrix was asked to adjudicate the forgery, agreed with it,
    and the verifier passed it. The statement the matrix actually saw is
    now its own field, and the claim has to match it.
    """
    from planbench_explanation.ledger_store import ClaimLedger
    from planbench_explanation.render import render_claim

    _, ledger = promoted_ledger()
    elsewhere = "the unrelated B9 passage is narrower than the required clearance"
    forged = ledger.claims[0].model_copy(update={"statement": elsewhere})

    payload = ledger.model_dump()
    payload["entries"][0]["claim"] = forged.model_dump()
    payload["entries"][0]["sentence"] = render_claim(forged)

    with pytest.raises((LedgerRefusal, ValidationError), match="the matrix adjudicated"):
        ClaimLedger.model_validate(payload)


def test_the_statement_the_matrix_saw_is_kept_for_refusals_too() -> None:
    """A refusal's wording is not the proposal's wording.

    The no-claim sentence carries only reasons, so nothing in a refused
    entry re-derives the statement — and the proposal's free text is a
    different sentence written for a different purpose. Falling back to
    it would re-adjudicate something that was never adjudicated.
    """
    tried = "the B7 passage is narrower than the required clearance"
    ledger = build_ledger(
        packet(),
        [(proposal(), record(status="check_failed", checker_results=()), tried)],
        catalog=CATALOG,
        scope=SCOPE,
    )
    entry = ledger.entries[0]
    assert entry.claim is None
    assert entry.promotion_statement == tried
    assert entry.promotion_statement != entry.proposal.hypothesis_statement


def test_a_ledger_relabelled_to_another_run_is_refused() -> None:
    """Whole-artifact comparison, not a list of fields somebody chose.

    ``run_id`` was not on the list, so this verified clean and quietly
    returned a rebuilt ledger carrying the real run's id — the file
    claiming one provenance, the verified object another.
    """
    from planbench_explanation.ledger_store import (
        ClaimLedger,
        LedgerVerificationFailure,
        verify_ledger,
    )

    built_packet, ledger = promoted_ledger()
    payload = ledger.model_dump()
    payload["run_id"] = "forged-run"

    with pytest.raises(LedgerVerificationFailure, match="run_id"):
        verify_ledger(
            ClaimLedger.model_validate(payload), built_packet, catalog=CATALOG, scope=SCOPE
        )


def test_a_verification_failure_names_where_the_file_and_the_matrix_part() -> None:
    """ "Verification failed" is not an audit; a path is."""
    from planbench_explanation.ledger_store import (
        ClaimLedger,
        LedgerVerificationFailure,
        verify_ledger,
    )

    built_packet, ledger = promoted_ledger()
    payload = ledger.model_dump()
    payload["header"] = {**payload["header"], "detector_version": "9.9.9"}

    with pytest.raises(LedgerVerificationFailure) as caught:
        verify_ledger(
            ClaimLedger.model_validate(payload), built_packet, catalog=CATALOG, scope=SCOPE
        )
    assert any("header.detector_version" in item for item in caught.value.mismatches)


def test_a_run_with_no_comparison_still_shows_its_traces() -> None:
    """No ΔU is not no evidence.

    A candidate that failed a gate has traces, and they are exactly what
    somebody asking "why did it fail" opens. Gating the whole viewer on
    the exemplars hid the evidence for the three outcomes whose only
    content is evidence.
    """
    for outcome in ("no_survivors", "gate_only"):
        plan = plan_for(outcome, has_comparison=False)  # type: ignore[arg-type]
        assert plan.show_trace_evidence
        assert not plan.show_exemplars

    interrupted = panel_for(ranked=False, status=None, interrupted=True, gate_only=False)
    assert interrupted.show_trace_evidence


def test_offering_exemplars_without_the_viewer_is_refused() -> None:
    with pytest.raises((PanelRefusal, ValidationError), match="links to nowhere"):
        PanelPlan(
            outcome="clear",
            show_waterfall=True,
            show_claims=True,
            show_exemplars=True,
            show_trace_evidence=False,
            show_gate_table=True,
            headline_key="explain.headline.clear",
        )
