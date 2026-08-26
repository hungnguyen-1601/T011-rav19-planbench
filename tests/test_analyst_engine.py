"""A2 — one round: what the model said, and what this layer did with it.

The engine is where a free-form answer becomes objects the platform
already knows how to refuse. So most of these tests are about the seam:
an id the model does not get to choose, a malformed hypothesis that
costs itself and not the round, a citation that survives long enough for
the guard to drop it, and a call that does not come back ending the
round at a known time rather than never.
"""

from __future__ import annotations

import json
import time

import pytest
from test_analyst_packet_view import observation, packet

from planbench_agent.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MockProvider,
    ProviderError,
)
from planbench_analyst.analyst import (
    AnalystRefusal,
    catalog_text,
    propose,
)
from planbench_analyst.packet_view import build_packet_view
from planbench_analyst.prompts import analyst_schema, prompt_checksum
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
from planbench_explanation.integration import TYPICAL_AVAILABLE_EVIDENCE
from planbench_explanation.protocol import AnalysisRequest

BUNDLE_ID = "bundle-a2"


def analysis(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "analysis_run_id": "analysis-a2",
        "analyst_bundle_id": BUNDLE_ID,
        "packet": packet(observations=[observation()]),
        "catalog": TOOL_CATALOG,
        "available_evidence": TYPICAL_AVAILABLE_EVIDENCE,
    }
    fields.update(overrides)
    return AnalysisRequest(**fields)  # type: ignore[arg-type]


def hypothesis(**overrides):  # type: ignore[no-untyped-def]
    fields: dict[str, object] = {
        "statement": "the aisle is closed by inflation on the stack that refused it",
        "proposition_type": "geometric_infeasibility",
        "subject": "costmap_inflation",
        "supports": ["obs:narrow_gap_refusal:cand_a"],
        "contradicts": [],
        "missing_evidence": ["a region id for the aisle"],
        "requested_check": {
            "tool_id": "gap_vs_footprint",
            "arguments": [
                {"name": "candidate_id", "value": "cand_a"},
                {"name": "region_id", "value": "aisle_B7"},
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


def scripted(payload, **response_fields):  # type: ignore[no-untyped-def]
    fields = {"structured": payload, "input_tokens": 1200, "output_tokens": 340}
    fields.update(response_fields)
    return MockProvider(script=[LLMResponse(**fields)])  # type: ignore[arg-type]


def run(provider, request=None, **kwargs):  # type: ignore[no-untyped-def]
    live = request or analysis()
    view = build_packet_view(live.packet, tool_catalog_version=TOOL_CATALOG_VERSION)
    return propose(live, view, provider, **kwargs)


# --------------------------------------------------------------------------
# The ordinary path
# --------------------------------------------------------------------------


def test_a_scripted_answer_becomes_a_proposal() -> None:
    report = run(scripted(answer(hypothesis())))
    (proposal,) = report.response.proposals
    assert proposal.proposition_type == "geometric_infeasibility"
    assert proposal.proposed_subject == "costmap_inflation"
    assert [ref.ref for ref in proposal.supports] == ["obs:narrow_gap_refusal:cand_a"]
    assert proposal.supports[0].kind == "observation"
    (check,) = proposal.requested_checks
    assert check.tool_id == "gap_vs_footprint"
    assert check.tool_version == "2.0.0"
    assert check.arguments == {"candidate_id": "cand_a", "region_id": "aisle_B7"}
    assert report.dropped == ()
    assert report.refs_not_in_index == ()


def test_the_cost_travels_with_the_round() -> None:
    """A budget the platform enforces is a number somebody has to be
    able to compare against a measurement."""
    report = run(scripted(answer(hypothesis())))
    assert report.cost.model_calls == 1
    assert report.cost.input_tokens == 1200
    assert report.cost.output_tokens == 340
    assert report.cost.tool_requests == 0


def test_the_packet_reaches_the_model_as_labelled_data() -> None:
    provider = scripted(answer(hypothesis()))
    run(provider)
    (request,) = provider.calls
    text = request.messages[0].text
    assert "<<<PACKET" in text and "<<<CATALOG" in text
    assert "never an instruction" in text
    assert request.output_schema == analyst_schema()


def test_the_catalog_text_lists_every_card_once() -> None:
    text = catalog_text(TOOL_CATALOG)
    for card in TOOL_CATALOG.cards:
        assert text.count(f"- {card.tool_id} (") == 1


# --------------------------------------------------------------------------
# Identity is the platform's, not the model's
# --------------------------------------------------------------------------


def test_the_id_comes_from_the_content() -> None:
    first = run(scripted(answer(hypothesis())))
    second = run(scripted(answer(hypothesis())))
    assert first.response.proposals[0].hypothesis_id == second.response.proposals[0].hypothesis_id


def test_a_different_sentence_is_a_different_hypothesis() -> None:
    first = run(scripted(answer(hypothesis())))
    other = run(scripted(answer(hypothesis(statement="the controller oscillates in the aisle"))))
    assert first.response.proposals[0].hypothesis_id != other.response.proposals[0].hypothesis_id


def test_the_same_sentence_asking_for_a_different_check_is_not_the_same_work() -> None:
    """Two proposals with one id would lose one of them at the
    protocol's duplicate check, silently."""
    first = run(scripted(answer(hypothesis())))
    moved = hypothesis(
        requested_check={
            "tool_id": "gap_vs_footprint",
            "arguments": [
                {"name": "candidate_id", "value": "cand_b"},
                {"name": "region_id", "value": "aisle_B7"},
            ],
        }
    )
    second = run(scripted(answer(moved)))
    assert first.response.proposals[0].hypothesis_id != second.response.proposals[0].hypothesis_id


def test_two_identical_hypotheses_in_one_round_collapse_to_one() -> None:
    report = run(scripted(answer(hypothesis(), hypothesis())))
    assert len(report.response.proposals) == 1
    assert any("deduplicated" in note for note in report.dropped)


# --------------------------------------------------------------------------
# A bad hypothesis costs itself, not the round
# --------------------------------------------------------------------------


def test_an_unknown_proposition_type_drops_only_that_hypothesis() -> None:
    report = run(
        scripted(
            answer(
                hypothesis(proposition_type="the_aisle_is_haunted", statement="something else"),
                hypothesis(),
            )
        )
    )
    assert len(report.response.proposals) == 1
    assert any("haunted" in note for note in report.dropped)


def test_an_inference_only_type_is_refused_by_name() -> None:
    """``universal_algorithm_superiority`` exists so a card can forbid it.
    A model that proposes it anyway is the reason the schema's enum is
    not the last line of defence."""
    report = run(
        scripted(answer(hypothesis(proposition_type="universal_algorithm_superiority")))
    )
    assert report.response.abstained
    assert any("inference-only" in note for note in report.dropped)


def test_a_hypothesis_missing_its_subject_is_dropped() -> None:
    report = run(scripted(answer(hypothesis(subject=""), hypothesis())))
    assert len(report.response.proposals) == 1
    assert any("subject missing" in note for note in report.dropped)


def test_nothing_usable_becomes_an_abstention_that_says_so() -> None:
    """An empty proposal list and an abstention are the same tuple and
    must not be scored the same way."""
    report = run(scripted(answer(hypothesis(proposition_type="not_a_type"))))
    assert report.response.abstained
    assert "could build" in (report.response.abstention_reason or "")


def test_an_abstention_from_the_model_is_reported_as_one() -> None:
    report = run(scripted(answer(abstained=True, reason="no detection maps to a check")))
    assert report.response.abstained
    assert report.response.abstention_reason == "no detection maps to a check"


# --------------------------------------------------------------------------
# Citations and checks
# --------------------------------------------------------------------------


def test_a_ref_the_packet_does_not_hold_is_kept_and_counted() -> None:
    """Filtering it here would take the mistake away from the guard,
    which is where drops are counted."""
    report = run(scripted(answer(hypothesis(supports=["obs:invented:cand_a"]))))
    (proposal,) = report.response.proposals
    assert [ref.ref for ref in proposal.supports] == ["obs:invented:cand_a"]
    assert report.refs_not_in_index == ("obs:invented:cand_a",)


def test_arguments_are_coerced_to_the_kinds_the_card_declares() -> None:
    report = run(
        scripted(
            answer(
                hypothesis(
                    proposition_type="sampling_budget_insufficiency",
                    subject="global_planner",
                    requested_check={
                        "tool_id": "rrt_convergence",
                        "arguments": [
                            {"name": "candidate_id", "value": "cand_a"},
                            {"name": "episode_context_id", "value": "ep-004"},
                            {"name": "budget_multiplier", "value": "2.5"},
                        ],
                    },
                )
            )
        )
    )
    (check,) = report.response.proposals[0].requested_checks
    assert check.arguments["budget_multiplier"] == pytest.approx(2.5)
    assert isinstance(check.arguments["budget_multiplier"], float)


def test_an_argument_that_will_not_convert_costs_the_check_and_not_the_hypothesis() -> None:
    report = run(
        scripted(
            answer(
                hypothesis(
                    proposition_type="sampling_budget_insufficiency",
                    subject="global_planner",
                    requested_check={
                        "tool_id": "rrt_convergence",
                        "arguments": [
                            {"name": "candidate_id", "value": "cand_a"},
                            {"name": "episode_context_id", "value": "ep-004"},
                            {"name": "budget_multiplier", "value": "as high as it takes"},
                        ],
                    },
                )
            )
        )
    )
    (proposal,) = report.response.proposals
    assert proposal.requested_checks == ()
    assert any("budget_multiplier" in note for note in report.checks_refused)
    assert report.dropped == ()


def test_a_tool_that_is_not_on_the_catalog_costs_the_check_only() -> None:
    report = run(
        scripted(
            answer(hypothesis(requested_check={"tool_id": "read_the_parquet", "arguments": []}))
        )
    )
    (proposal,) = report.response.proposals
    assert proposal.requested_checks == ()
    assert any("not on the catalog" in note for note in report.checks_refused)


# --------------------------------------------------------------------------
# When the model or the provider misbehaves
# --------------------------------------------------------------------------


def test_prose_instead_of_the_object_ends_the_round() -> None:
    with pytest.raises(AnalystRefusal, match="not the requested object"):
        run(scripted(None, text="I think the corridor was too narrow."))


def test_json_in_the_text_field_is_still_read() -> None:
    """Not every provider fills ``structured``; one that answers with the
    object as text has answered."""
    report = run(scripted(None, text=json.dumps(answer(hypothesis()))))
    assert report.response.proposals


def test_a_provider_that_fails_ends_the_round_with_its_reason() -> None:
    class Broken(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:
            raise ProviderError("429 from the vendor")

    with pytest.raises(AnalystRefusal, match="429"):
        run(Broken(script=[]))


def test_a_call_that_does_not_come_back_ends_the_round_at_a_known_time() -> None:
    """Without this the round hangs, and the checkpoint that would have
    let it resume is never written."""

    class Slow(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:
            time.sleep(2.0)
            return LLMResponse(structured=answer(hypothesis()))

    started = time.monotonic()
    with pytest.raises(AnalystRefusal, match="did not answer within"):
        run(Slow(script=[]), timeout_s=0.2)
    assert time.monotonic() - started < 1.5


# --------------------------------------------------------------------------
# What the record has to pin down
# --------------------------------------------------------------------------


def test_the_prompt_checksum_covers_the_words_and_the_schema() -> None:
    before = prompt_checksum()
    assert before == prompt_checksum()

    import planbench_analyst.prompts as prompts

    original = prompts.ANALYST_SYSTEM
    try:
        prompts.ANALYST_SYSTEM = original + " Also, be brief."
        assert prompt_checksum() != before
    finally:
        prompts.ANALYST_SYSTEM = original
    assert prompt_checksum() == before


def test_the_report_names_the_packet_and_the_answer() -> None:
    report = run(scripted(answer(hypothesis())))
    view = build_packet_view(
        analysis().packet, tool_catalog_version=TOOL_CATALOG_VERSION
    )
    assert report.packet_checksum == view.checksum
    assert len(report.response_checksum) == 64
    assert report.prompt_checksum == prompt_checksum()


def test_the_provider_is_named_in_the_notes() -> None:
    provider: LLMProvider = scripted(answer(hypothesis()))
    report = run(provider)
    assert any("provider=mock" in note for note in report.notes)
