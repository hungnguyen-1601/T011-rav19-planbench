"""A4 — the seam, and the loop that runs on it.

Two things are held here. That a request and a host are built from the
same evidence, because building them separately is how every tool ends
up refused for missing evidence the host is sitting on. And that the
loop stops — four ways, each named, each ending at exactly one
``finalize`` event.
"""

from __future__ import annotations

import pytest
from test_analyst_packet_view import observation, packet

from planbench_agent.provider import LLMResponse, MockProvider
from planbench_analyst.round_host import (
    PreparedRound,
    evidence_for,
    in_process_round,
)
from planbench_analyst.runner import run_round
from planbench_explanation.budget import PLATFORM_BUDGET_CAP
from planbench_explanation.bundle import AnalystBundle
from planbench_explanation.case_packet import RobotFacts, TaskFacts
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.packet_artifact import (
    PacketArtifact,
    PacketProvenance,
    packet_checksum,
)
from planbench_explanation.protocol import ANALYST_RUNNER_PROTOCOL_VERSION


def bundle(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "bundle_id": "bundle-a4",
        "agent_code_digest": "git:" + "a" * 40,
        "container_digest": "sha256:" + "b" * 64,
        "model_id": "claude-opus-5",
        "model_revision": "2026-05-01",
        "prompt_checksum": "c" * 64,
        "rag_index_version": "kb-index-3",
        "retrieval_config_checksum": "d" * 64,
        "tool_catalog_version": TOOL_CATALOG_VERSION,
        "generation_parameters": {"temperature": 0.0},
        "runner_protocol_version": ANALYST_RUNNER_PROTOCOL_VERSION,
        "requested_budget": PLATFORM_BUDGET_CAP,
        "created_at": "2026-08-26T09:30:00Z",
    }
    fields.update(overrides)
    return AnalystBundle(**fields)  # type: ignore[arg-type]


#: A run whose route was measured against the map, so the geometry a
#: clearance check needs actually exists. Without it the seam correctly
#: withholds ``region_geometry`` and every map request is refused — which
#: is the seam working, and would make these tests about the wrong thing.
MEASURED_TASK = TaskFacts(
    task_profile_id="warehouse_a_v1",
    robot=RobotFacts(radius_m=0.26, inflation_margin_m=0.11, required_passage_width_m=0.74),
    route=RouteFeatures(
        narrowest_passage_m=0.71,
        narrowest_at_progress_m=4.0,
        narrowest_lower_bound_m=0.71,
        obstacle_density=0.2,
        density_band_m=1.0,
        route_length_m=12.0,
        unmeasured_samples=0,
        samples_limited_by_coverage=0,
    ),
)


def artifact(built=None, *, sidecar: bool = True) -> PacketArtifact:  # type: ignore[no-untyped-def]
    built = built or packet(observations=[observation()], task=MEASURED_TASK)
    return PacketArtifact(
        case_id="case-1",
        packet=built,
        provenance=PacketProvenance(
            packet_ref="fixtures/golden/visible/case-1/packet.json",
            packet_checksum=packet_checksum(built),
            run_id=built.run_id,
            recorded_at="2026-08-26T09:00:00Z",
            sidecar_present=sidecar,
            source="planted_run",
        ),
    )


def prepared(**overrides) -> PreparedRound:  # type: ignore[no-untyped-def]
    fields = {
        "supplied": artifact(),
        "bundle": bundle(),
        "catalog": TOOL_CATALOG,
        "analysis_run_id": "analysis-a4",
    }
    fields.update(overrides)
    supplied = fields.pop("supplied")
    target = fields.pop("bundle")
    return in_process_round(supplied, target, **fields)  # type: ignore[arg-type]


def hypothesis(**overrides):  # type: ignore[no-untyped-def]
    fields: dict[str, object] = {
        "statement": "the refusals on cand_a are consistent with the aisle closing",
        "proposition_type": "geometric_infeasibility",
        "subject": "costmap_inflation",
        "supports": ["obs:narrow_gap_refusal:cand_a"],
        "contradicts": [],
        "missing_evidence": [],
        "requested_check": {
            "tool_id": "get_map_region_features",
            "arguments": [
                {"name": "region_id", "value": "aisle_B7"},
                {"name": "candidate_id", "value": "cand_a"},
            ],
        },
        "recommended_experiments": [],
    }
    fields.update(overrides)
    return fields


def answer(*hypotheses, abstained: bool = False, reason: str = ""):  # type: ignore[no-untyped-def]
    return {
        "abstained": abstained,
        "abstention_reason": reason,
        "hypotheses": list(hypotheses),
    }


def scripted(*payloads):  # type: ignore[no-untyped-def]
    return MockProvider(
        script=[
            LLMResponse(structured=payload, input_tokens=900, output_tokens=200)
            for payload in payloads
        ]
    )


# --------------------------------------------------------------------------
# The seam
# --------------------------------------------------------------------------


def test_the_request_and_the_host_are_built_from_one_source() -> None:
    """Build the request first and the host second — the obvious order —
    and every tool dies at ``missing_required_evidence`` while the host
    is sitting on the evidence."""
    round_ = prepared()
    assert round_.analysis.available_evidence
    assert "map_checksum" in round_.analysis.available_evidence
    assert round_.evidence_identity_checksum


def test_a_run_without_the_sidecar_offers_fewer_tools() -> None:
    """The replay-based checks are not servable, and an analyst that
    assumes otherwise finds out at admission."""
    with_sidecar = prepared().analysis.available_evidence
    without = prepared(supplied=artifact(sidecar=False)).analysis.available_evidence
    assert "trace" in with_sidecar
    assert "trace" not in without


def test_a_bare_packet_is_assumed_to_have_no_sidecar() -> None:
    """The honest default when provenance is missing is the smaller set:
    assuming otherwise hands the analyst tools the run cannot serve."""
    built = packet(observations=[observation()], task=MEASURED_TASK)
    assert "trace" not in prepared(supplied=built).analysis.available_evidence


def test_the_available_set_is_derived_from_what_the_packet_holds() -> None:
    """A caller that passes its own set is a caller that can widen it,
    and the party most motivated to widen it is the one being graded."""
    no_route = evidence_for(packet(observations=[observation()]), sidecar_present=True)
    assert "region_geometry" not in no_route.available_evidence


def test_two_reads_of_one_source_have_one_identity() -> None:
    assert prepared().evidence_identity_checksum == prepared().evidence_identity_checksum


def test_the_prepared_round_carries_both_budgets() -> None:
    round_ = prepared()
    assert round_.requested_budget_checksum == PLATFORM_BUDGET_CAP.checksum
    assert round_.effective_budget_checksum == PLATFORM_BUDGET_CAP.checksum


# --------------------------------------------------------------------------
# The loop, and its four endings
# --------------------------------------------------------------------------


def test_a_round_with_nothing_left_to_ask_ends_final() -> None:
    outcome = run_round(prepared(), scripted(answer(hypothesis(requested_check=None))))
    assert outcome.stopped_because == "final"
    assert outcome.events[-1] == "finalize:final"


def test_an_abstention_ends_the_round_immediately() -> None:
    outcome = run_round(
        prepared(), scripted(answer(abstained=True, reason="nothing maps to a check"))
    )
    assert outcome.response.abstained
    assert outcome.stopped_because == "final"
    assert outcome.cost.tool_requests == 0


def test_a_check_is_run_and_its_result_comes_back() -> None:
    outcome = run_round(prepared(), scripted(answer(hypothesis()), answer(hypothesis())))
    assert outcome.cost.tool_requests == 1
    assert outcome.results
    assert any(event.startswith("result:") for event in outcome.events)


def test_asking_for_the_same_check_again_stops_the_round() -> None:
    """The checkers are deterministic: the second call returns what the
    first returned, so the round would pay a model call to learn
    nothing. This is the failure a retry loop wears as diligence."""
    outcome = run_round(prepared(), scripted(answer(hypothesis()), answer(hypothesis())))
    assert outcome.stopped_because == "no_progress"
    assert outcome.events[-1] == "finalize:no_progress"


def test_a_model_that_keeps_finding_new_checks_runs_out_of_revisions() -> None:
    first = hypothesis()
    second = hypothesis(
        statement="the refusals on cand_a are consistent with a narrow corridor",
        requested_check={
            "tool_id": "get_candidate_contrast",
            "arguments": [
                {"name": "candidate_a", "value": "cand_a"},
                {"name": "candidate_b", "value": "cand_b"},
            ],
        },
    )
    third = hypothesis(
        statement="the refusals on cand_a are consistent with the inflation margin",
        requested_check={"tool_id": "get_known_unknowns", "arguments": []},
    )
    outcome = run_round(
        prepared(),
        scripted(answer(first), answer(second), answer(third)),
        max_revisions=2,
    )
    assert outcome.stopped_because == "revisions_exhausted"
    assert outcome.cost.model_calls == 3


def test_the_model_call_budget_ends_the_round_as_its_own_ending() -> None:
    """"I had nothing to say" and "I was stopped" are different answers
    and must not score the same."""
    tight = PLATFORM_BUDGET_CAP.model_copy(update={"max_model_calls": 1})
    outcome = run_round(
        prepared(bundle=bundle(requested_budget=tight)),
        scripted(answer(hypothesis()), answer(hypothesis())),
        max_revisions=3,
    )
    assert outcome.stopped_because == "budget_exceeded"
    assert "budget:model_calls" in outcome.events


def test_the_tool_budget_stops_the_requests_and_says_so() -> None:
    tight = PLATFORM_BUDGET_CAP.model_copy(update={"max_tool_requests": 1})
    two = [
        hypothesis(),
        hypothesis(
            statement="the refusals on cand_a are consistent with a narrow corridor",
            requested_check={
                "tool_id": "get_candidate_contrast",
                "arguments": [
                    {"name": "candidate_a", "value": "cand_a"},
                    {"name": "candidate_b", "value": "cand_b"},
                ],
            },
        ),
    ]
    outcome = run_round(
        prepared(bundle=bundle(requested_budget=tight)), scripted(answer(*two))
    )
    assert outcome.cost.tool_requests == 1
    assert outcome.stopped_because == "budget_exceeded"


def test_a_provider_failure_ends_the_round_as_an_abstention_with_a_reason() -> None:
    outcome = run_round(prepared(), MockProvider(script=[]))
    assert outcome.response.abstained
    assert outcome.stopped_because == "model_failed"
    assert "could not be completed" in (outcome.response.abstention_reason or "")


# --------------------------------------------------------------------------
# Invariants of the loop
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payloads",
    [
        (answer(hypothesis(requested_check=None)),),
        (answer(abstained=True, reason="nothing here"),),
        (answer(hypothesis()), answer(hypothesis())),
    ],
)
def test_every_ending_goes_through_exactly_one_finalize(payloads) -> None:  # type: ignore[no-untyped-def]
    outcome = run_round(prepared(), scripted(*payloads))
    assert sum(1 for event in outcome.events if event.startswith("finalize:")) == 1


def test_proposals_are_declared_before_any_request_is_made() -> None:
    """A request that arrives before its proposal was declared is refused
    as ``unknown_hypothesis``, and the refusal reads as the platform
    being broken."""
    outcome = run_round(prepared(), scripted(answer(hypothesis()), answer(hypothesis())))
    declared = next(i for i, event in enumerate(outcome.events) if event.startswith("declared:"))
    first_result = next(
        (i for i, event in enumerate(outcome.events) if event.startswith("result:")), None
    )
    assert first_result is not None
    assert declared < first_result
    assert not outcome.rejections


def test_what_the_guard_dropped_is_visible_on_the_round() -> None:
    outcome = run_round(
        prepared(),
        scripted(answer(hypothesis(statement="the aisle is 0.71 m wide"))),
    )
    assert outcome.response.abstained
    assert "blocked:quantity_in_statement" in outcome.events
