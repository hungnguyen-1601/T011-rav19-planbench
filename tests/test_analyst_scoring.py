"""B1 — how a round becomes the endpoints the preregistration named.

The arithmetic is small and every line of it is a place a number could
quietly mean something else. A case that is right two times in three is
not two thirds correct; a mechanism named without its component is not a
correct mechanism; declining an answerable case is wrong in a way that
looks safe; and a draft is a sentence written before its evidence
arrived, so nothing is scored on one.
"""

from __future__ import annotations

from test_analyst_packet_view import observation, packet
from test_analyst_runner import MEASURED_TASK, answer, hypothesis, prepared, scripted

from planbench_analyst.eval_spec import CaseLabels
from planbench_analyst.packet_view import build_packet_view
from planbench_analyst.runner import run_round
from planbench_analyst.scoring import score_case, score_repeat
from planbench_explanation.catalog import TOOL_CATALOG_VERSION


def label(**overrides) -> CaseLabels:  # type: ignore[no-untyped-def]
    fields = {
        "case_id": "case-1",
        "expected_mechanism": "geometric_infeasibility",
        "expected_subject": "costmap_inflation",
        "acceptable_refs": [{"ref_prefix": "obs:narrow_gap_refusal:"}],
        "acceptable_tools": ["gap_vs_footprint"],
        "expect_abstention": False,
        "expected_check_required": True,
    }
    fields.update(overrides)
    return CaseLabels(**fields)  # type: ignore[arg-type]


def view():  # type: ignore[no-untyped-def]
    return build_packet_view(
        packet(observations=[observation()], task=MEASURED_TASK),
        tool_catalog_version=TOOL_CATALOG_VERSION,
    )


def scored(payload=None, **kwargs):  # type: ignore[no-untyped-def]
    outcome = run_round(prepared(), scripted(payload or answer(hypothesis())), **kwargs)
    return score_repeat("case-1", outcome, label(), view()), outcome


def final(**overrides):  # type: ignore[no-untyped-def]
    fields = hypothesis(**overrides)
    fields["decision"] = "no_check"
    fields.pop("requested_check", None)
    return fields


# --------------------------------------------------------------------------
# One repeat
# --------------------------------------------------------------------------


def test_a_final_statement_with_the_planted_mechanism_scores_correct() -> None:
    result, _ = scored(answer(final()))
    assert result.mechanism_correct
    assert result.subject_correct


def test_a_draft_is_not_scored() -> None:
    """A CheckPlan statement exists only because the host binds evidence
    to a declared hypothesis; scoring it would score a sentence written
    before its evidence arrived.

    The round has to **end** holding a draft for this to test anything —
    three turns, each asking for a different check, so the last one is
    still a draft when the revisions run out. An earlier version of this
    let the provider run dry, which ended the round abstaining and made
    the assertion pass for the wrong reason.
    """
    turns = [
        answer(
            hypothesis(
                requested_check={
                    "tool_id": "gap_vs_footprint",
                    "arguments": [
                        {"name": "candidate_id", "value": "cand_a"},
                        {"name": "region_id", "value": f"aisle_B{index}"},
                    ],
                }
            )
        )
        for index in range(1, 5)
    ]
    outcome = run_round(prepared(), scripted(*turns))
    assert outcome.stopped_because == "revisions_exhausted"
    assert any(proposal.requested_checks for proposal in outcome.response.proposals)
    result = score_repeat("case-1", outcome, label(), view())
    assert not result.mechanism_correct


def test_the_right_mechanism_on_the_wrong_component_is_not_correct() -> None:
    """Otherwise "something in the stack is starved" counts as an
    answer."""
    payload = final(subject="global_planner", supports=["obs:narrow_gap_refusal:cand_a"])
    result, _ = scored(answer(payload))
    assert result.mechanism_correct != result.subject_correct or not result.subject_correct


def test_an_abstention_on_an_answerable_case_is_wrong() -> None:
    """Wrong in a way that looks safe."""
    result, _ = scored(answer(abstained=True, reason="not enough evidence"))
    assert not result.abstention_correct
    assert not result.mechanism_correct


def test_an_abstention_the_labels_expected_is_right() -> None:
    outcome = run_round(prepared(), scripted(answer(abstained=True, reason="nothing here")))
    result = score_repeat("case-1", outcome, label(expect_abstention=True), view())
    assert result.abstention_correct


def test_a_case_with_no_label_scores_zero_rather_than_passing() -> None:
    """A suite that quietly lost its labels must report zero, not a
    perfect score."""
    outcome = run_round(prepared(), scripted(answer(final())))
    result = score_repeat("case-1", outcome, None, view())
    assert not result.mechanism_correct
    assert not result.abstention_correct


def test_what_the_guard_dropped_is_counted_as_a_structural_violation() -> None:
    payload = final(statement="the inflation caused every refusal on this map")
    result, _ = scored(answer(payload))
    assert result.structural_violations >= 1


def test_the_tokens_and_calls_travel_with_the_score() -> None:
    result, outcome = scored()
    assert result.cost_tokens == outcome.cost.input_tokens + outcome.cost.output_tokens
    assert result.model_calls == outcome.cost.model_calls


# --------------------------------------------------------------------------
# The case, across repeats
# --------------------------------------------------------------------------


def test_a_case_is_correct_only_when_every_repeat_was() -> None:
    """Two out of three is not two thirds of a case: reliability is a
    different endpoint with its own number."""
    good, _ = scored(answer(final()))
    bad, _ = scored(answer(abstained=True, reason="not enough"))
    assert score_case("case-1", [good, good, good]).mechanism_correct
    assert not score_case("case-1", [good, bad, good]).mechanism_correct


def test_a_case_that_disagreed_with_itself_is_marked_unstable() -> None:
    """ "Wrong every time" and "right once out of three" are different
    problems, and only the second is a reliability problem."""
    good, _ = scored(answer(final()))
    bad, _ = scored(answer(abstained=True, reason="not enough"))
    assert score_case("case-1", [good, good]).stable
    assert not score_case("case-1", [good, bad]).stable


def test_the_median_cost_is_over_the_repeats_that_ran() -> None:
    good, _ = scored(answer(final()))
    assert score_case("case-1", [good, good]).median_tokens == good.cost_tokens


def test_a_case_with_no_repeats_is_not_silently_correct() -> None:
    empty = score_case("case-1", [])
    assert not empty.mechanism_correct
    assert not empty.abstention_correct
