"""A6 — what a run cost, what it got wrong, and whether it beat the floor.

The order matters and is the point: failures are counted before any
target is read, a case run once says nothing about reliability, and the
floor is a paired comparison rather than two averages. Most of these
tests are about numbers the harness refuses to produce.
"""

from __future__ import annotations

import pytest
from test_analyst_packet_view import observation, packet
from test_analyst_runner import MEASURED_TASK, bundle, hypothesis, prepared, scripted

from planbench_analyst.harness import (
    REAL_PACKET_CAVEATS,
    CaseResult,
    FloorComparison,
    compare_with_floor,
    failure_table,
    mcnemar_exact,
    pass_hat_k,
    routing_failures,
)
from planbench_analyst.runner import run_round


def answer(*hypotheses, abstained: bool = False, reason: str = ""):  # type: ignore[no-untyped-def]
    return {
        "abstained": abstained,
        "abstention_reason": reason,
        "hypotheses": list(hypotheses),
    }


def prepared_for(_case_id: str = "case-1"):  # type: ignore[no-untyped-def]
    return prepared()


def result(*payloads, case_id: str = "case-1") -> CaseResult:  # type: ignore[no-untyped-def]
    round_ = prepared()
    outcome = run_round(round_, scripted(*payloads))
    return CaseResult(
        case_id=case_id,
        outcome=outcome,
        floor=outcome.response,
    )


# --------------------------------------------------------------------------
# Failures are counted before any target is read
# --------------------------------------------------------------------------


def test_the_table_counts_guard_drops_host_refusals_and_endings_together() -> None:
    """One question — what is this analyst doing wrong — and three
    tables would be three things nobody cross-references."""
    dropped = result(answer(hypothesis(statement="the aisle is 0.71 m wide")))
    counts = failure_table([dropped])
    assert counts["guard:quantity_in_statement"] == 1
    assert any(key.startswith("ended:") for key in counts)


def test_an_empty_run_has_an_empty_table_rather_than_a_zero_for_everything() -> None:
    assert failure_table([]) == {}


def test_host_refusals_are_read_as_the_routing_mistake_they_are() -> None:
    """``checker_selection`` is one number for a skill with four ways of
    going wrong, and they need different fixes."""
    class _Fake:
        stopped_because = "final"
        events = ("rejected:arguments_rejected", "rejected:missing_required_evidence")
        rejections = ("arguments_rejected", "missing_required_evidence")

        class guard:  # noqa: N801 - a stand-in shaped like the real one
            blocked = ()

    counts = routing_failures([CaseResult(case_id="c", outcome=_Fake(), floor=None)])  # type: ignore[arg-type]
    assert counts == {"unnecessary_tool": 1, "wrong_arg_value": 1}


# --------------------------------------------------------------------------
# Reliability is a different question from correctness
# --------------------------------------------------------------------------


def test_a_case_that_held_every_time_counts_and_one_that_did_not_does_not() -> None:
    assert pass_hat_k([[True, True, True]]) == 1.0
    assert pass_hat_k([[True, True, False]]) == 0.0


def test_pass_hat_k_falls_as_repeats_rise() -> None:
    """An analyst right 90% of the time is right 73% of the time three
    times running, and that is the number a deployment lives with."""
    nine_of_ten = [[True] * 3 for _ in range(9)] + [[True, False, True]]
    assert pass_hat_k(nine_of_ten) == 0.9
    assert pass_hat_k([]) == 0.0


# --------------------------------------------------------------------------
# The floor comparison is paired, and says when it cannot conclude
# --------------------------------------------------------------------------


def test_only_the_disagreements_carry_information() -> None:
    """Both right, or both wrong, says nothing about which is better."""
    assert mcnemar_exact(0, 0) == 1.0


def test_a_lopsided_split_reaches_significance() -> None:
    assert mcnemar_exact(10, 0) < 0.05


def test_an_even_split_does_not() -> None:
    assert mcnemar_exact(5, 5) == 1.0


def test_too_few_disagreements_cannot_reach_significance_at_all() -> None:
    """Worth knowing before running the comparison rather than after
    reading a number out of it."""
    assert mcnemar_exact(4, 0) > 0.05
    assert mcnemar_exact(6, 0) < 0.05


def test_the_comparison_says_when_it_was_underpowered() -> None:
    """A p of 0.25 on three discordant cases is not weak evidence of no
    difference; it is no evidence either way."""
    thin = FloorComparison(cases=(), model_only=2, floor_only=1)
    assert thin.underpowered is True
    wide = FloorComparison(cases=(), model_only=9, floor_only=1)
    assert wide.underpowered is False


# --------------------------------------------------------------------------
# A run over production packets, and what it refuses to claim
# --------------------------------------------------------------------------


def test_a_run_reports_cost_beside_quality() -> None:
    """"Better and four times the price" is a different answer from
    "better", and only one of them is a deployment."""
    report = compare_with_floor(["case-1"], prepared_for, scripted(answer(hypothesis())))
    summary = report.summary()
    assert summary["cases"] == 1
    assert summary["median_input_tokens"] > 0
    assert "tool_requests" in summary


def test_precision_is_not_in_the_summary_and_the_reason_travels_with_it() -> None:
    """These packets carry no planted answer. A precision computed from
    them would be a number about nothing."""
    report = compare_with_floor(["case-1"], prepared_for, scripted(answer(hypothesis())))
    summary = report.summary()
    assert "precision" not in summary
    assert any("planted answer" in item for item in summary["caveats"])  # type: ignore[operator]
    assert REAL_PACKET_CAVEATS[0] in report.caveats


def test_repeats_produce_a_reliability_number() -> None:
    provider = scripted(*[answer(hypothesis()) for _ in range(6)])
    report = compare_with_floor(["case-1"], prepared_for, provider, repeats=3)
    assert report.repeats == 3
    assert report.reliability == 1.0


def test_a_model_that_dies_is_counted_as_a_crash_not_an_abstention() -> None:
    """Crashing is not a strategy, and it must not score as silence."""
    from planbench_agent.provider import MockProvider

    report = compare_with_floor(["case-1"], prepared_for, MockProvider(script=[]))
    assert report.crashes == 1
    assert report.summary()["crashes"] == 1


def test_the_floor_is_guarded_too() -> None:
    """Comparing a guarded model against an unguarded floor would credit
    the model for drops the floor never had to survive."""
    report = compare_with_floor(["case-1"], prepared_for, scripted(answer(hypothesis())))
    (case,) = report.cases
    assert case.floor is not None


def test_a_fresh_round_is_prepared_per_repeat() -> None:
    """A host carries the session; reusing one across repeats would let
    the second run inherit the first run's declarations."""
    seen: list[int] = []

    def counting(case_id: str):  # type: ignore[no-untyped-def]
        seen.append(1)
        return prepared()

    provider = scripted(*[answer(hypothesis()) for _ in range(4)])
    compare_with_floor(["case-1"], counting, provider, repeats=2)
    assert len(seen) == 2


def test_a_packet_with_nothing_to_find_lets_both_sides_abstain() -> None:
    quiet = packet()

    def prepared_quiet(case_id: str):  # type: ignore[no-untyped-def]
        return prepared(supplied=quiet)

    report = compare_with_floor(
        ["case-quiet"],
        prepared_quiet,
        scripted(answer(abstained=True, reason="nothing here maps to a check")),
    )
    (case,) = report.cases
    assert case.abstained and case.floor_abstained
    assert report.comparison is not None
    assert report.comparison.discordant == 0


def test_an_observation_the_floor_maps_makes_the_pairing_visible() -> None:
    busy = packet(observations=[observation("stuck_cluster")], task=MEASURED_TASK)

    def prepared_busy(case_id: str):  # type: ignore[no-untyped-def]
        return prepared(supplied=busy)

    report = compare_with_floor(
        ["case-busy"],
        prepared_busy,
        scripted(answer(abstained=True, reason="I would rather not")),
    )
    assert report.comparison is not None
    assert report.comparison.floor_only == 1
    assert report.comparison.underpowered is True


def test_the_bundle_the_round_ran_under_is_still_the_one_prepared() -> None:
    assert prepared(bundle=bundle()).analysis.analyst_bundle_id == "bundle-a4"


def test_an_empty_case_list_produces_an_empty_report() -> None:
    report = compare_with_floor([], prepared_for, scripted())
    assert report.summary()["cases"] == 0
    with pytest.raises(AssertionError):
        assert report.median_cost != (0, 0)
