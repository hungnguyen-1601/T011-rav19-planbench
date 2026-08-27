"""W4 — the answer says which branch it is on, and a draft stays a draft.

Before this, one shape carried two different things: a statement whose
evidence was already in the packet, and a statement written *before* the
check that was supposed to support it. They read identically, and the
second one is only allowed to exist at all because the host binds
evidence to a hypothesis that was declared first.

So the answer declares a branch, the parser refuses a mismatch by name —
which is what makes a single repair turn possible — the guard refuses a
draft that reports a verdict nobody has run yet, and the transcript
carries the link from a superseded draft to what replaced it.
"""

from __future__ import annotations

from test_analyst_runner import answer, hypothesis, prepared, scripted

from planbench_analyst.harness import branch_matrix, cost_by_class
from planbench_analyst.runner import run_round


def malformed(**overrides):  # type: ignore[no-untyped-def]
    fields = hypothesis()
    fields.update(overrides)
    return fields


# --------------------------------------------------------------------------
# The union
# --------------------------------------------------------------------------


def test_a_final_statement_that_also_asks_for_a_check_is_refused() -> None:
    """A final statement is one whose evidence is already in hand."""
    outcome = run_round(prepared(), scripted(answer(malformed(decision="no_check"))))
    assert outcome.reports[0].dropped
    assert "no_check" in outcome.reports[0].dropped[0]


def test_a_check_branch_that_names_no_tool_is_refused() -> None:
    """A draft exists only because a check is coming."""
    payload = hypothesis()
    payload["decision"] = "check"
    payload.pop("requested_check", None)
    outcome = run_round(prepared(), scripted(answer(payload)))
    assert outcome.reports[0].dropped
    assert "names no tool" in outcome.reports[0].dropped[0]


def test_an_answer_with_no_branch_at_all_is_refused() -> None:
    payload = hypothesis()
    payload.pop("decision")
    outcome = run_round(prepared(), scripted(answer(payload)))
    assert any("decision" in item for item in outcome.reports[0].dropped)


def test_a_well_formed_check_branch_is_declared_as_a_draft() -> None:
    outcome = run_round(prepared(), scripted(answer(hypothesis())))
    assert any(event.startswith("draft:") for event in outcome.events)


def test_a_well_formed_no_check_branch_is_declared_as_final() -> None:
    payload = hypothesis()
    payload["decision"] = "no_check"
    payload.pop("requested_check")
    outcome = run_round(prepared(), scripted(answer(payload)))
    assert any(event.startswith("final:") for event in outcome.events)


# --------------------------------------------------------------------------
# Repair: once, and counted
# --------------------------------------------------------------------------


def test_a_malformed_answer_buys_exactly_one_repair_turn() -> None:
    outcome = run_round(
        prepared(),
        scripted(answer(malformed(decision="no_check")), answer(hypothesis())),
    )
    repairs = [event for event in outcome.events if event.startswith("repair:")]
    assert len(repairs) == 1


def test_the_repair_is_a_model_call_and_is_counted_as_one() -> None:
    """Otherwise it is a retry wearing another word, and the rule is that
    a case gets one attempt."""
    once = run_round(prepared(), scripted(answer(hypothesis())))
    repaired = run_round(
        prepared(),
        scripted(answer(malformed(decision="no_check")), answer(hypothesis())),
    )
    assert repaired.cost.model_calls > once.cost.model_calls


def test_a_second_malformed_answer_does_not_buy_a_second_repair() -> None:
    """A loop that repairs until it parses is a loop that pays for
    agreement."""
    outcome = run_round(
        prepared(),
        scripted(
            answer(malformed(decision="no_check")),
            answer(malformed(decision="no_check")),
            answer(hypothesis()),
        ),
    )
    assert len([event for event in outcome.events if event.startswith("repair:")]) == 1


def test_an_abstention_is_not_repaired() -> None:
    outcome = run_round(prepared(), scripted(answer(abstained=True, reason="not enough")))
    assert not any(event.startswith("repair:") for event in outcome.events)


# --------------------------------------------------------------------------
# The draft contract
# --------------------------------------------------------------------------


def test_a_draft_that_reports_its_own_verdict_is_blocked() -> None:
    """The words are the ones a real verdict would use, which is why
    nothing downstream could tell the two apart afterwards."""
    payload = hypothesis(
        statement="the aisle is closed by inflation, as the check confirmed on this run"
    )
    outcome = run_round(prepared(), scripted(answer(payload)))
    assert any(item.rule == "draft_claims_a_verdict" for item in outcome.guard.blocked)


def test_a_final_statement_is_not_held_to_the_draft_rule() -> None:
    payload = hypothesis(statement="the refusals are associated with the inflated passage")
    payload["decision"] = "no_check"
    payload.pop("requested_check")
    outcome = run_round(prepared(), scripted(answer(payload)))
    assert not any(item.rule == "draft_claims_a_verdict" for item in outcome.guard.blocked)


def test_a_revised_statement_carries_the_link_to_what_it_replaced() -> None:
    """Rewriting under the old id is already impossible: different
    content is a different name. What was missing is the line saying
    which draft this replaced."""
    revised = hypothesis(statement="the refusals are associated with the measured passage")
    revised["decision"] = "no_check"
    revised.pop("requested_check")
    outcome = run_round(prepared(), scripted(answer(hypothesis()), answer(revised)))
    assert any(event.startswith("supersedes:") for event in outcome.events)


# --------------------------------------------------------------------------
# Cost by a class fixed before the run
# --------------------------------------------------------------------------


def test_cost_is_reported_by_the_class_the_labels_fixed() -> None:
    """Reporting by the branch the model chose would compare two
    populations picked after seeing the outcome."""
    from pathlib import Path

    from planbench_analyst.eval_spec import load_eval_spec
    from planbench_analyst.harness import CaseResult

    spec = load_eval_spec(
        Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "labels" / "visible.json"
    )
    outcome = run_round(prepared(), scripted(answer(hypothesis())))
    rows = [
        CaseResult(case_id="inflation-001", outcome=outcome, floor=outcome.response),
        CaseResult(case_id="dwa-001", outcome=outcome, floor=outcome.response),
    ]
    summary = cost_by_class(rows, spec)
    assert summary["check_required"]["cases"] == 1
    assert summary["no_check_required"]["cases"] == 1
    assert summary["check_required"]["median_tokens"] > 0


def test_the_branch_the_model_took_is_reported_as_a_diagnostic() -> None:
    from pathlib import Path

    from planbench_analyst.eval_spec import load_eval_spec
    from planbench_analyst.harness import CaseResult

    spec = load_eval_spec(
        Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "labels" / "visible.json"
    )
    outcome = run_round(prepared(), scripted(answer(hypothesis())))
    rows = [CaseResult(case_id="inflation-001", outcome=outcome, floor=outcome.response)]
    matrix = branch_matrix(rows, spec)
    assert matrix["check_required"]["check"] + matrix["check_required"]["no_check"] == 1
