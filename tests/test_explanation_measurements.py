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

from planbench_explanation.exemplars import Exemplar, ExemplarSet
from planbench_explanation.packet_builder import (
    TIMELINE_MARKS,
    TIMELINE_ROLES,
    EpisodeTrace,
    gate_rows_from_report,
    measurements_from_report,
    timelines_from_traces,
)
from planbench_explanation.running_metrics import Deployment


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
    """ "No collisions" and "nobody counted collisions" are different
    sentences, and a zero here would merge them."""
    measured = only(measurements_from_report(report(episodes=[])))
    assert measured.collisions is None
    assert measured.min_clearance_m is None
    assert measured.success_rate is not None


def test_a_rate_with_no_denominator_in_the_report_is_dropped_rather_than_guessed() -> None:
    measured = only(measurements_from_report(report(n_distinct_episodes=None, n_episodes=None)))
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


# --------------------------------------------------------------------------
# M2 — how the exemplar episodes went while they were going
# --------------------------------------------------------------------------


def deployment() -> Deployment:
    return Deployment(
        robot_radius_m=0.26,
        control_period_s=0.05,
        clearance_warning_m=0.35,
        max_linear_velocity=0.8,
        reference_length_m=12.0,
    )


def trace(episode_context_id: str = "ep-001", *, columns=None) -> EpisodeTrace:
    rows = 20
    default = {
        "t": [index * 0.1 for index in range(rows)],
        "x": [index * 0.5 for index in range(rows)],
        "y": [0.0] * rows,
        "clearance_m": [0.6 - index * 0.02 for index in range(rows)],
        "planner_latency_ms": [10.0 + index for index in range(rows)],
        "progress_m": [index * 0.6 for index in range(rows)],
    }
    return EpisodeTrace(
        candidate_id="cand_a",
        episode_context_id=episode_context_id,
        columns=columns if columns is not None else default,
    )


def exemplar_set(*episode_ids: str) -> ExemplarSet:
    roles = ("typical", "strongest_for_winner", "strongest_for_runnerup", "safety_critical")
    chosen = list(episode_ids) + [f"ep-{index:03d}" for index in range(len(episode_ids), 4)]
    return ExemplarSet(
        candidate_a="cand_a",
        candidate_b="cand_b",
        n_episodes=30,
        exemplars=tuple(
            Exemplar(role=role, episode_context_id=episode_id, delta_utility=0.0, criterion=0.0)
            for role, episode_id in zip(roles, chosen, strict=True)
        ),
    )


def test_an_exemplar_episode_gets_a_timeline_on_both_clocks() -> None:
    built, omissions = timelines_from_traces(
        [trace("ep-001")], exemplar_set("ep-001"), deployment()
    )
    assert omissions == ()
    (timeline,) = built
    assert timeline.role == "typical"
    clocks = {point.clock for point in timeline.points}
    assert clocks == {"at_time", "at_progress"}


def test_only_two_roles_are_carried() -> None:
    """The two ΔU extremes are already described by the waterfall; what a
    timeline adds is the shape of a representative episode and of the
    one that came closest to something."""
    built, _ = timelines_from_traces(
        [trace("ep-001"), trace("ep-002"), trace("ep-003")],
        exemplar_set("ep-001", "ep-002", "ep-003"),
        deployment(),
    )
    carried = {item.role for item in built}
    assert carried <= set(TIMELINE_ROLES)
    assert "strongest_for_winner" not in carried
    assert "strongest_for_runnerup" not in carried


def test_an_episode_nobody_chose_gets_no_timeline() -> None:
    built, _ = timelines_from_traces([trace("ep-999")], exemplar_set("ep-001"), deployment())
    assert built == ()


def test_a_trace_missing_a_column_is_skipped_and_said_so() -> None:
    """Building a slice out of half the columns would report a different
    moment of the episode than the one asked for."""
    broken = trace("ep-001", columns={"t": [0.0, 0.1], "x": [0.0, 0.5]})
    built, omissions = timelines_from_traces([broken], exemplar_set("ep-001"), deployment())
    assert built == ()
    assert any("missing a column" in item for item in omissions)


def test_a_run_with_no_deployment_thresholds_says_why_it_has_no_timeline() -> None:
    built, omissions = timelines_from_traces([trace()], exemplar_set("ep-001"), None)
    assert built == ()
    assert omissions


def test_the_two_clocks_are_never_the_same_row() -> None:
    """At equal wall-clock time the robots are at different places on the
    task; at equal progress they are at the same place having taken
    different times."""
    built, _ = timelines_from_traces([trace("ep-001")], exemplar_set("ep-001"), deployment())
    (timeline,) = built
    at_time = [point for point in timeline.points if point.clock == "at_time"]
    at_progress = [point for point in timeline.points if point.clock == "at_progress"]
    assert len(at_time) == len(at_progress) == len(TIMELINE_MARKS)
    assert [point.mark for point in at_progress] == list(TIMELINE_MARKS)
