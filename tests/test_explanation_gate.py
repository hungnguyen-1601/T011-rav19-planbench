"""E6b — the gate harness: one frozen analyst, one hidden suite, one decision.

What these guard: a gate refuses the suite the submitter calibrated on;
it refuses a bundle frozen against a different wire contract; an analyst
that raises is scored rather than skipped; the decision carries the
preregistered bar rather than one the run chose; and a recorded run can
be re-checked against the bundle and bar it claims.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_decision.objectives import PREFERENCE_PROFILES
from planbench_explanation.bundle import (
    CALIBRATION_TARGETS,
    AnalystBundle,
    BundleRefusal,
    MetricTargets,
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
from planbench_explanation.gate import (
    GateRefusal,
    gate_summary,
    run_gate,
    verify_gate_run,
)
from planbench_explanation.golden import ExpectedFinding, GoldenSuite, PlantedCase
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.ledger import HypothesisProposal, KnownUnknown
from planbench_explanation.protocol import AnalysisRequest, AnalysisResponse, ToolSession
from planbench_explanation.versioning import ExplanationArtifactHeader
from planbench_explanation.waterfall import (
    ObjectiveLevels,
    UtilityDrillDown,
    Waterfall,
    WaterfallBar,
    WaterfallProfile,
)

PREREG = "docs/preregistration/analyst-gate-1.md"
DECIDED = "2026-08-20T10:00:00Z"


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


def packet(run_id: str = "run_017", **overrides) -> CasePacket:  # type: ignore[no-untyped-def]
    fields = {
        "run_id": run_id,
        "header": header(),
        "task": TaskFacts(
            task_profile_id="warehouse_a_v1",
            robot=RobotFacts(radius_m=0.26, inflation_margin_m=0.11, required_passage_width_m=0.74),
        ),
        "candidates": [stack("cand_a"), stack("cand_b", "rrtstar")],
        "decision": DecisionFacts(status="CLEAR_RECOMMENDATION", waterfall=waterfall()),
    }
    fields.update(overrides)
    return build_case_packet(**fields)  # type: ignore[arg-type]


def bundle(**overrides) -> AnalystBundle:  # type: ignore[no-untyped-def]
    fields = {
        "bundle_id": "bundle-017",
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


def planted(case_id: str, **overrides) -> PlantedCase:  # type: ignore[no-untyped-def]
    fields = {
        "case_id": case_id,
        "family": "inflation_gap_closure",
        "variant": "positive",
        "packet_ref": f"fixtures/{case_id}/packet.json",
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


def hidden_suite(*cases: PlantedCase) -> GoldenSuite:
    return GoldenSuite(
        suite_version="hidden-1.0.0",
        visibility="hidden",
        status="calibration",
        cases=cases or (planted("case-1"),),
    )


def packets_from(mapping=None):  # type: ignore[no-untyped-def]
    store = mapping or {}

    def source(case: PlantedCase) -> CasePacket:
        return store.get(case.case_id) or packet()

    return source


def sessions(analysis: AnalysisRequest) -> ToolSession:
    return ToolSession(analysis)


def finding_analyst(analysis: AnalysisRequest) -> AnalysisResponse:
    """Proposes the planted mechanism, every time."""
    return AnalysisResponse(
        analysis_run_id=analysis.analysis_run_id,
        analyst_bundle_id=analysis.analyst_bundle_id,
        proposals=(
            HypothesisProposal(
                hypothesis_id="hyp-1",
                hypothesis_statement="the aisle is closed by inflation",
                proposition_type="geometric_infeasibility",
                proposed_subject="costmap_inflation",
            ),
        ),
    )


def crashing_analyst(analysis: AnalysisRequest) -> AnalysisResponse:
    raise RuntimeError("the model timed out")


def gate(suite=None, analyst=finding_analyst, **overrides):  # type: ignore[no-untyped-def]
    fields = {
        "analyst": analyst,
        "packets": packets_from(),
        "sessions": sessions,
        "catalog": TOOL_CATALOG,
        "targets": CALIBRATION_TARGETS,
        "preregistration_ref": PREREG,
        "decided_at": DECIDED,
    }
    fields.update(overrides)
    return run_gate(bundle(), suite or hidden_suite(), **fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# What a gate refuses to do
# --------------------------------------------------------------------------


def test_a_gate_will_not_grade_on_the_calibration_set() -> None:
    """It measures how well the submitter fitted the set it was given."""
    visible = GoldenSuite(
        suite_version="calibration-0.1.0",
        visibility="visible",
        status="calibration",
        cases=(planted("case-1"),),
    )
    with pytest.raises(GateRefusal, match="calibrated on"):
        gate(visible)


def test_a_dry_run_against_the_visible_set_is_possible_and_named_as_such() -> None:
    visible = GoldenSuite(
        suite_version="calibration-0.1.0",
        visibility="visible",
        status="calibration",
        cases=(planted("case-1"),),
    )
    run = gate(visible, allow_visible_suite=True)
    assert run.suite_version == "calibration-0.1.0"


def test_a_bundle_frozen_against_another_wire_contract_is_refused() -> None:
    """A contract that moved is a different system under the same name."""
    with pytest.raises(GateRefusal, match="wire contract"):
        run_gate(
            bundle(tool_catalog_version="1.0.0"),
            hidden_suite(),
            analyst=finding_analyst,
            packets=packets_from(),
            sessions=sessions,
            catalog=TOOL_CATALOG,
            targets=CALIBRATION_TARGETS,
            preregistration_ref=PREREG,
            decided_at=DECIDED,
        )


# --------------------------------------------------------------------------
# What it records
# --------------------------------------------------------------------------


def test_the_decision_is_about_the_bundle_and_the_suite_that_ran() -> None:
    run = gate()
    assert run.decision.bundle_identity_checksum == bundle().identity_checksum
    assert run.decision.hidden_suite_version == "hidden-1.0.0"
    assert run.decision.targets_checksum == CALIBRATION_TARGETS.checksum


def test_the_decision_reports_the_whole_preregistered_bar() -> None:
    """Not the metrics that happened to clear."""
    from planbench_explanation.bundle import REQUIRED_GATE_METRICS

    run = gate()
    assert {row.metric for row in run.decision.metrics} == set(REQUIRED_GATE_METRICS)


def test_an_analyst_that_raises_is_scored_rather_than_skipped() -> None:
    """Crashing on the hard cases must not improve the score."""
    run = gate(hidden_suite(planted("case-1"), planted("case-2")), analyst=crashing_analyst)
    assert run.failed_cases == ("case-1", "case-2")
    assert not run.score.clean
    assert not run.decision.passes(CALIBRATION_TARGETS)


def test_one_crash_among_several_cases_is_recorded_on_the_decision() -> None:
    calls = {"n": 0}

    def flaky(analysis: AnalysisRequest) -> AnalysisResponse:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("timed out")
        return finding_analyst(analysis)

    run = gate(hidden_suite(planted("case-1"), planted("case-2")), analyst=flaky)
    assert run.failed_cases == ("case-2",)
    assert any("case-2" in note for note in run.decision.notes)


def test_a_leak_is_read_off_the_packet_the_analyst_was_shown() -> None:
    """Grading a rule nobody was shown grades what it could not have known."""
    blocked = packet(
        extra_unknowns=[
            KnownUnknown(
                id="geometry_gap",
                blocks_claim_types=("geometric_infeasibility",),
                source="H4",
            )
        ]
    )
    run = gate(packets=packets_from({"case-1": blocked}))
    (outcome,) = run.outcomes
    assert outcome.submission.blocked_claim_leaks == ("hyp-1:geometric_infeasibility",)
    assert not run.score.clean


def test_the_tools_scored_come_from_the_hosts_account_of_the_round() -> None:
    """Never from the analyst's own account of itself."""
    run = gate()
    (outcome,) = run.outcomes
    assert outcome.submission.requested_tool_ids == ()


# --------------------------------------------------------------------------
# Reading it back
# --------------------------------------------------------------------------


def test_a_run_can_be_re_checked_against_the_bundle_it_claims() -> None:
    run = gate()
    verify_gate_run(run, bundle=bundle(), targets=CALIBRATION_TARGETS)


def test_a_run_checked_against_another_bundle_is_refused() -> None:
    run = gate()
    with pytest.raises(BundleRefusal, match="different configuration"):
        verify_gate_run(run, bundle=bundle(prompt_checksum="f" * 64), targets=CALIBRATION_TARGETS)


def test_a_run_checked_against_another_bar_is_refused() -> None:
    run = gate()
    with pytest.raises(BundleRefusal, match="different bar"):
        verify_gate_run(run, bundle=bundle(), targets=MetricTargets(precision=0.1))


def test_the_summary_reports_the_numbers_the_decision_was_made_on() -> None:
    """A summary computed a second way is a second answer waiting to disagree."""
    run = gate()
    summary = gate_summary(run, CALIBRATION_TARGETS)
    assert summary["bundle_id"] == "bundle-017"
    assert set(summary["metrics"]) == {row.metric for row in run.decision.metrics}
    for name, row in summary["metrics"].items():
        recorded = next(item for item in run.decision.metrics if item.metric == name)
        assert row["value"] == recorded.value
        assert row["threshold"] == recorded.threshold


# --------------------------------------------------------------------------
# The record has to be about the run that produced it
# --------------------------------------------------------------------------


def test_a_decision_naming_another_bundle_is_refused() -> None:
    """The two halves are assembled separately and stored together."""
    from planbench_explanation.gate import GateRun

    run = gate()
    other = run.decision.model_copy(update={"bundle_identity_checksum": "f" * 64})
    # Pydantic wraps a validator's refusal, so the type at the boundary
    # is ValidationError carrying the GateRefusal message.
    with pytest.raises(ValidationError, match="different bundle identity"):
        GateRun(**{**run.model_dump(), "decision": other})


def test_a_decision_naming_another_suite_is_refused() -> None:
    """A score earned on one suite, filed against a different one, is a
    number about a run nobody made. The check existed; nothing exercised
    it, so removing it left every test in this file green."""
    from planbench_explanation.gate import GateRun

    run = gate()
    other = run.decision.model_copy(update={"hidden_suite_version": "hidden-9.9.9"})
    with pytest.raises(ValidationError, match="different suite"):
        GateRun(**{**run.model_dump(), "decision": other})
