"""E4.3 — comparing two candidates while an episode plays.

What these guard: the two clocks are never mixed; a running minimum does
not recover; exposure is measured in seconds rather than samples; the
composite is the platform's own objective curves rather than a second
opinion; and it is never called ΔU, because ``U_R`` has no value halfway
through an episode.
"""

from __future__ import annotations

import pytest

from planbench_decision.anchors import load_anchors
from planbench_decision.objectives import DecisionSettings
from planbench_explanation.running_metrics import (
    PROGRESS_SYNC_METRICS,
    TIME_SYNC_METRICS,
    Deployment,
    RunningMetricsRefusal,
    TraceSlice,
    compare_at_progress,
    compare_at_time,
    partial_utility,
    sample_at,
)


@pytest.fixture(scope="module")
def anchors():  # type: ignore[no-untyped-def]
    from planbench_benchmark.task_map import load_task_map  # noqa: F401
    from pathlib import Path

    import yaml

    from planbench_schemas.task_profile import TaskProfile

    path = Path(__file__).resolve().parents[1] / "profiles" / "open_hall_v1.yaml"
    profile = TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    return load_anchors().resolve(profile)


DEPLOYMENT = Deployment(
    robot_radius_m=0.25,
    control_period_s=0.05,
    clearance_warning_m=0.5,
    max_linear_velocity=1.0,
    reference_length_m=10.0,
)


def straight(candidate_id: str, *, clearances=None, latencies=None, steps: int = 11) -> TraceSlice:
    """A run down the reference line at one metre per second."""
    times = tuple(float(index) for index in range(steps))
    return TraceSlice(
        candidate_id=candidate_id,
        t=times,
        x=tuple(float(index) for index in range(steps)),
        y=tuple(0.0 for _ in range(steps)),
        clearance_m=tuple(clearances or [1.0] * steps),
        planner_latency_ms=tuple(latencies or [10.0] * steps),
        progress_m=tuple(float(index) for index in range(steps)),
    )


# --------------------------------------------------------------------------
# The two clocks
# --------------------------------------------------------------------------


def test_the_schema_says_which_clock_each_metric_belongs_to() -> None:
    """The wrong pairing yields a number that looks fine and means nothing."""
    assert "safety_margin" in PROGRESS_SYNC_METRICS
    assert "safety_margin" not in TIME_SYNC_METRICS
    assert "progress_fraction" in TIME_SYNC_METRICS
    assert not set(TIME_SYNC_METRICS) & set(PROGRESS_SYNC_METRICS)


def test_at_equal_time_the_comparison_is_who_is_ahead(anchors) -> None:  # type: ignore[no-untyped-def]
    fast = straight("fast")
    slow = TraceSlice(
        candidate_id="slow",
        t=tuple(float(index) for index in range(11)),
        x=tuple(index * 0.5 for index in range(11)),
        y=tuple(0.0 for _ in range(11)),
        clearance_m=tuple([1.0] * 11),
        planner_latency_ms=tuple([10.0] * 11),
        progress_m=tuple(index * 0.5 for index in range(11)),
    )
    comparison = compare_at_time(
        fast, slow, 6.0, deployment=DEPLOYMENT, settings=DecisionSettings(), anchors=anchors
    )
    assert comparison is not None
    assert comparison.a.progress_fraction > comparison.b.progress_fraction


def test_at_equal_progress_the_comparison_is_who_did_it_better(anchors) -> None:  # type: ignore[no-untyped-def]
    """Same stretch of world, same obstacles met — the difference is the stack."""
    quick = straight("quick")
    dawdler = TraceSlice(
        candidate_id="dawdler",
        t=tuple(index * 2.0 for index in range(11)),
        x=tuple(float(index) for index in range(11)),
        y=tuple(0.0 for _ in range(11)),
        clearance_m=tuple([1.0] * 11),
        planner_latency_ms=tuple([10.0] * 11),
        progress_m=tuple(float(index) for index in range(11)),
    )
    comparison = compare_at_progress(
        quick, dawdler, 5.0, deployment=DEPLOYMENT, settings=DecisionSettings(), anchors=anchors
    )
    assert comparison is not None
    assert comparison.a.elapsed_s < comparison.b.elapsed_s
    assert comparison.a.progress_fraction == pytest.approx(comparison.b.progress_fraction)


def test_a_run_that_never_reached_that_progress_has_nothing_to_compare(anchors) -> None:  # type: ignore[no-untyped-def]
    short = straight("short", steps=4)
    comparison = compare_at_progress(
        straight("long"),
        short,
        8.0,
        deployment=DEPLOYMENT,
        settings=DecisionSettings(),
        anchors=anchors,
    )
    assert comparison is None


def test_before_both_runs_have_started_there_is_no_comparison(anchors) -> None:  # type: ignore[no-untyped-def]
    late = TraceSlice(
        candidate_id="late",
        t=(5.0, 6.0),
        x=(0.0, 1.0),
        y=(0.0, 0.0),
        clearance_m=(1.0, 1.0),
        planner_latency_ms=(10.0, 10.0),
        progress_m=(0.0, 1.0),
    )
    assert (
        compare_at_time(
            straight("early"),
            late,
            1.0,
            deployment=DEPLOYMENT,
            settings=DecisionSettings(),
            anchors=anchors,
        )
        is None
    )


# --------------------------------------------------------------------------
# What each quantity actually says
# --------------------------------------------------------------------------


def test_the_worst_clearance_does_not_recover(anchors) -> None:  # type: ignore[no-untyped-def]
    """Safety is a worst case; a number that heals forgets the near miss."""
    dipped = straight("dipped", clearances=[1.0, 1.0, 0.1, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    after = sample_at(dipped, 9, deployment=DEPLOYMENT)
    assert after.safety_margin == pytest.approx(0.1 / 0.25)


def test_exposure_is_seconds_rather_than_samples() -> None:
    """A loop that ticks twice as often would otherwise look twice as exposed."""
    close = [0.2] * 11
    coarse = straight("coarse", clearances=close)
    fine = TraceSlice(
        candidate_id="fine",
        t=tuple(index * 0.5 for index in range(21)),
        x=tuple(index * 0.5 for index in range(21)),
        y=tuple(0.0 for _ in range(21)),
        clearance_m=tuple([0.2] * 21),
        planner_latency_ms=tuple([10.0] * 21),
        progress_m=tuple(index * 0.5 for index in range(21)),
    )
    assert sample_at(coarse, 10, deployment=DEPLOYMENT).exposure_s == pytest.approx(
        sample_at(fine, 20, deployment=DEPLOYMENT).exposure_s
    )


def test_compute_is_measured_against_the_deployments_own_budget() -> None:
    """1.0 means the same thing in every episode: at G4's threshold."""
    at_budget = straight("at_budget", latencies=[50.0] * 11)
    assert sample_at(at_budget, 10, deployment=DEPLOYMENT).compute_budget == pytest.approx(1.0)


def test_progress_rate_is_not_speed() -> None:
    """A robot oscillating at full speed has speed and no progress."""
    stuck = TraceSlice(
        candidate_id="stuck",
        t=tuple(float(index) for index in range(11)),
        x=tuple(1.0 + (index % 2) * 0.3 for index in range(11)),
        y=tuple(0.0 for _ in range(11)),
        clearance_m=tuple([1.0] * 11),
        planner_latency_ms=tuple([10.0] * 11),
        progress_m=tuple([1.0] * 11),
    )
    assert sample_at(stuck, 10, deployment=DEPLOYMENT).progress_rate == pytest.approx(0.0)
    assert sample_at(stuck, 10, deployment=DEPLOYMENT).path_efficiency < 1.0


def test_a_straight_run_is_perfectly_efficient() -> None:
    assert sample_at(straight("a"), 10, deployment=DEPLOYMENT).path_efficiency == pytest.approx(1.0)


def test_no_metric_reads_a_planner_specific_counter() -> None:
    """A* has expanded nodes, RRT* has a tree, a policy has neither."""
    fields = set(sample_at(straight("a"), 5, deployment=DEPLOYMENT).model_dump())
    assert not {"expanded_nodes", "tree_nodes", "iterations"} & fields


# --------------------------------------------------------------------------
# The composite
# --------------------------------------------------------------------------


def test_the_composite_uses_the_platforms_own_objective_curves(anchors) -> None:  # type: ignore[no-untyped-def]
    """Not a second opinion that happens to end up nearby.

    Computed by calling ``_safety`` and ``_efficiency`` with prefix
    inputs, so an anchor moving moves this too — which is the property a
    parallel implementation would lose.
    """
    from planbench_decision.objectives import _efficiency, _safety

    settings = DecisionSettings()
    run = straight("a")
    value = partial_utility(run, 10, deployment=DEPLOYMENT, settings=settings, anchors=anchors)

    u_s = _safety(anchors, 0.0, 1.0)
    u_e = _efficiency(anchors, settings, 1.0, 1.0)
    weights = settings.weights
    expected = (weights.w_s * u_s + weights.w_e * u_e) / (weights.w_s + weights.w_e)
    assert value == pytest.approx(expected)


def test_the_composite_names_the_objectives_it_covers(anchors) -> None:  # type: ignore[no-untyped-def]
    """A reader must never be left assuming it was all four."""
    comparison = compare_at_time(
        straight("a"),
        straight("b"),
        5.0,
        deployment=DEPLOYMENT,
        settings=DecisionSettings(),
        anchors=anchors,
    )
    assert comparison is not None
    assert comparison.partial_objectives == ("U_S", "U_E")
    assert "U_R" not in comparison.partial_objectives


def test_the_safer_run_holds_the_advantage(anchors) -> None:  # type: ignore[no-untyped-def]
    """Two identical runs but one grazed a wall."""
    settings = DecisionSettings()
    clean = straight("clean")
    grazed = straight("grazed", clearances=[1.0, 1.0, 0.05, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    comparison = compare_at_progress(
        clean, grazed, 9.0, deployment=DEPLOYMENT, settings=settings, anchors=anchors
    )
    assert comparison is not None
    assert comparison.partial_advantage > 0


def test_two_identical_runs_have_no_advantage_either_way(anchors) -> None:  # type: ignore[no-untyped-def]
    comparison = compare_at_time(
        straight("a"),
        straight("b"),
        7.0,
        deployment=DEPLOYMENT,
        settings=DecisionSettings(),
        anchors=anchors,
    )
    assert comparison is not None
    assert comparison.partial_advantage == pytest.approx(0.0)


def test_an_empty_slice_is_refused_rather_than_scored(anchors) -> None:  # type: ignore[no-untyped-def]
    empty = TraceSlice(
        candidate_id="empty",
        t=(),
        x=(),
        y=(),
        clearance_m=(),
        planner_latency_ms=(),
        progress_m=(),
    )
    with pytest.raises(RunningMetricsRefusal, match="no samples"):
        sample_at(empty, 0, deployment=DEPLOYMENT)


def test_the_composite_measures_efficiency_against_the_replay_s_reference_line(anchors) -> None:  # type: ignore[no-untyped-def]
    """Not against ``L_ref``, and the difference is real.

    The episode metrics divide by the shortest route the map allows;
    this divides by progress along the line the replay is synchronised
    on, which E2 takes from the planned path. Where the two lines differ
    the ratios differ, so the running number *tracks* the episode's
    rather than converging to it — which is why the panel hands over to
    the stored value at the end instead of letting this one stand.
    """
    settings = DecisionSettings()
    run = straight("a")

    # Same trace, two deployments that disagree only about how long the
    # reference line is. The composite moves, which it could not do if
    # it were measuring against a property of the map.
    short_line = partial_utility(
        run, 10, deployment=DEPLOYMENT, settings=settings, anchors=anchors
    )
    assert short_line > 0

    # Progress halved against the same driven distance: a route the
    # replay considers twice as wandering.
    wandering = TraceSlice(
        candidate_id="a",
        t=run.t,
        x=run.x,
        y=run.y,
        clearance_m=run.clearance_m,
        planner_latency_ms=run.planner_latency_ms,
        progress_m=tuple(value / 2 for value in run.progress_m),
    )
    assert (
        partial_utility(wandering, 10, deployment=DEPLOYMENT, settings=settings, anchors=anchors)
        < short_line
    )
