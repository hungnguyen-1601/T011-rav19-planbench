"""M1 — reading what a run scored out of the report it already wrote.

The numbers were always there. They lived in ``comparison_report.json``
and never reached the packet, so an analyst could talk about the ΔU
decomposition and not about what either candidate did — which is the
first thing a reader asking "why did this one win" wants.

What these tests hold is the honesty of the reading: a rate carries its
denominator, a field the run did not record stays absent rather than
becoming zero, and a gate whose shape nobody wrote down here contributes
its verdict and no invented numbers.
"""

from __future__ import annotations

from planbench_explanation.packet_builder import (
    gate_rows_from_report,
    measurements_from_report,
)


def report(**overrides):  # type: ignore[no-untyped-def]
    candidate = {
        "candidate_id": "cand_a",
        "n_distinct_episodes": 30,
        "n_episodes": 30,
        "success_rate": 0.7,
        "pooled_p99_latency_ms": 19.3,
        "decision_utility": 0.78,
        "episodes": [
            {"collision_count": 0, "min_clearance": 0.31},
            {"collision_count": 1, "min_clearance": 0.2617},
        ],
        "gates": {
            "candidate_id": "cand_a",
            "G1": "pass",
            "G4": {"result": "pass", "p99_ms": 19.3, "threshold_ms": 50.0},
            "G5": {"result": "pass", "status": "estimated_from_structure"},
        },
    }
    candidate.update(overrides)
    return {"candidates": [candidate]}


def only(rows):  # type: ignore[no-untyped-def]
    (row,) = rows
    return row


# --------------------------------------------------------------------------
# Measurements
# --------------------------------------------------------------------------


def test_a_rate_arrives_with_the_episodes_behind_it() -> None:
    measured = only(measurements_from_report(report()))
    assert measured.success_rate is not None
    assert measured.success_rate.value == 0.7
    assert measured.success_rate.denominator == 30


def test_the_latency_tail_reaches_the_packet() -> None:
    """This is the number the outcome rules pair with a sampling
    planner's textbook price, and until now the analyst could not see
    it at all."""
    measured = only(measurements_from_report(report()))
    assert measured.latency_p99_ms is not None
    assert measured.latency_p99_ms.unit == "ms"


def test_collisions_are_summed_and_clearance_is_the_worst_one() -> None:
    measured = only(measurements_from_report(report()))
    assert measured.collisions is not None
    assert measured.collisions.value == 1.0
    assert measured.min_clearance_m is not None
    assert measured.min_clearance_m.value == 0.2617


def test_a_field_the_run_did_not_record_stays_absent() -> None:
    """"No collisions" and "nobody counted collisions" are different
    sentences, and a zero here would merge them."""
    measured = only(measurements_from_report(report(episodes=[])))
    assert measured.collisions is None
    assert measured.min_clearance_m is None
    assert measured.success_rate is not None


def test_a_rate_with_no_denominator_in_the_report_is_dropped_rather_than_guessed() -> None:
    measured = only(
        measurements_from_report(report(n_distinct_episodes=None, n_episodes=None))
    )
    assert measured.success_rate is None
    assert measured.latency_p99_ms is not None


def test_a_report_with_no_candidates_yields_nothing() -> None:
    assert measurements_from_report({"candidates": []}) == ()
    assert measurements_from_report({}) == ()


# --------------------------------------------------------------------------
# Gate rows
# --------------------------------------------------------------------------


def test_a_gate_with_a_threshold_arrives_with_both_halves() -> None:
    rows = {row.gate_id: row for row in gate_rows_from_report(report())}
    assert rows["G4"].value == 19.3
    assert rows["G4"].threshold == 50.0
    assert rows["G4"].direction == "at_most"
    assert rows["G4"].unit == "ms"


def test_a_bare_pass_is_a_verdict_and_nothing_more() -> None:
    rows = {row.gate_id: row for row in gate_rows_from_report(report())}
    assert rows["G1"].passed is True
    assert rows["G1"].threshold is None


def test_a_gate_shape_nobody_wrote_down_contributes_no_numbers() -> None:
    """Inventing a threshold from an unfamiliar key would put a number
    in the packet that the run never compared anything against."""
    rows = {row.gate_id: row for row in gate_rows_from_report(report())}
    assert rows["G5"].passed is True
    assert rows["G5"].value is None


def test_every_row_says_whose_gate_it_was() -> None:
    """A gate table is per candidate, and a row that did not say which
    one would be a verdict about nobody."""
    assert all(row.candidate_id == "cand_a" for row in gate_rows_from_report(report()))


def test_a_failing_gate_reads_as_failing() -> None:
    failing = report(
        gates={
            "candidate_id": "cand_a",
            "G2": {"result": "fail", "n_distinct_episodes": 5, "n_min": 30},
        }
    )
    (row,) = gate_rows_from_report(failing)
    assert row.passed is False
    assert row.direction == "at_least"
    assert row.value == 5.0
