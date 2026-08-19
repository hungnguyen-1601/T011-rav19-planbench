"""E2 — lining two replays up, and refusing to pretend they line up.

The failure this guards is not a wrong pixel. It is a viewer that shows
two robots at "the same place" and lets a reader conclude they faced the
same situation, when the only thing making the panels agree is a
reference line nobody could produce.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_explanation.replay_sync import (
    ANCHOR_EVENTS,
    PROGRESS_SYNC_WARNING,
    ProgressSyncPlan,
    ProjectedPath,
    ProjectedSample,
    ReferenceLine,
    ReplaySyncRefusal,
    TrackPoint,
    build_progress_sync,
    choose_reference,
    find_divergence,
    project,
)

CORRIDOR = [(0.0, 0.0), (10.0, 0.0)]


def straight_track(*, speed: float, offset: float = 0.0, steps: int = 11) -> list[TrackPoint]:
    """A run down the corridor at constant speed, held at one offset."""
    return [TrackPoint(time=index / speed, x=float(index), y=offset) for index in range(steps)]


# --------------------------------------------------------------------------
# The reference line, and saying which one it is
# --------------------------------------------------------------------------


def test_the_planner_path_is_preferred_and_says_so() -> None:
    line = choose_reference(planned_path=CORRIDOR, candidate_path=[(0.0, 1.0), (9.0, 1.0)])
    assert line.quality == "reference_plan"
    assert not line.is_degraded
    assert line.length_m == pytest.approx(10.0)


def test_without_a_plan_the_fallbacks_are_labelled_not_hidden() -> None:
    """Each step down is recorded, and the caller still gets a usable line."""
    driven = choose_reference(planned_path=None, candidate_path=[(0.0, 0.0), (8.0, 2.0)])
    assert driven.quality == "degraded_candidate_path"
    assert driven.is_degraded

    straight = choose_reference(
        planned_path=None, candidate_path=None, start=(0.0, 0.0), goal=(10.0, 0.0)
    )
    assert straight.quality == "degraded_straight_line"
    assert straight.is_degraded


def test_a_stopped_robots_repeated_pose_is_not_a_reference_line() -> None:
    """A path of one distinct point projects everything to progress 0."""
    with pytest.raises(ReplaySyncRefusal):
        choose_reference(planned_path=None, candidate_path=[(1.0, 1.0)] * 50)

    with pytest.raises(ReplaySyncRefusal):
        choose_reference(planned_path=None, candidate_path=None, start=(1.0, 1.0), goal=(1.0, 1.0))

    with pytest.raises(ReplaySyncRefusal):
        choose_reference(planned_path=None)


def test_a_zero_length_reference_is_refused_outright() -> None:
    with pytest.raises(ValidationError):
        ReferenceLine(points=((2.0, 2.0), (2.0, 2.0)), quality="reference_plan")
    with pytest.raises(ValidationError):
        ReferenceLine(points=((0.0, 0.0),), quality="reference_plan")


def test_quality_has_no_default() -> None:
    """ "Did not say" must not be readable as "reference plan"."""
    with pytest.raises(ValidationError):
        ReferenceLine(points=tuple(CORRIDOR))  # type: ignore[call-arg]


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------


def test_progress_is_arc_length_and_offset_is_signed() -> None:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    left = project([TrackPoint(time=1.0, x=3.0, y=0.4)], line).samples[0]
    right = project([TrackPoint(time=1.0, x=3.0, y=-0.4)], line).samples[0]

    assert left.progress_m == pytest.approx(3.0)
    assert right.progress_m == pytest.approx(3.0)
    # Same distance, opposite sides — two runs passing an obstacle on
    # different sides is the case ``|e|`` would erase.
    assert left.cross_track_m == pytest.approx(0.4)
    assert right.cross_track_m == pytest.approx(-0.4)


def test_reversing_out_of_a_dead_end_is_counted_not_hidden() -> None:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    track = [
        TrackPoint(time=0.0, x=0.0, y=0.0),
        TrackPoint(time=1.0, x=4.0, y=0.0),
        TrackPoint(time=2.0, x=2.0, y=0.0),  # backed up
        TrackPoint(time=3.0, x=6.0, y=0.0),
    ]
    path = project(track, line)

    assert path.backward_samples == 1
    # Interpolation runs on the running maximum, so the ladder never
    # goes down even though the robot did.
    assert path.monotone_progress == pytest.approx((0.0, 4.0, 4.0, 6.0))


def test_a_run_that_stopped_short_has_no_time_for_ground_it_never_covered() -> None:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    path = project(straight_track(speed=1.0, steps=5), line)

    assert path.time_at_progress(2.0) == pytest.approx(2.0)
    assert path.time_at_progress(9.0) is None


def test_an_empty_trajectory_projects_to_nothing() -> None:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    with pytest.raises(ReplaySyncRefusal):
        project([], line)
    with pytest.raises(ValidationError):
        ProjectedPath(samples=(), backward_samples=0)


# --------------------------------------------------------------------------
# Progress-sync, and the warning it cannot be separated from
# --------------------------------------------------------------------------


def plan_for(speed_a: float, speed_b: float, *, offset_b: float = 0.0) -> ProgressSyncPlan:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    return build_progress_sync(
        project(straight_track(speed=speed_a), line),
        project(straight_track(speed=speed_b, offset=offset_b), line),
        reference=line,
        steps=21,
    )


def test_progress_sync_puts_the_two_runs_on_arc_length_not_the_clock() -> None:
    """Half the speed, same place, twice the timestamp."""
    plan = plan_for(1.0, 0.5)
    row = next(row for row in plan.rows if row.progress_m == pytest.approx(5.0))

    assert row.time_a == pytest.approx(5.0)
    assert row.time_b == pytest.approx(10.0)
    assert plan.common_progress_m == pytest.approx(10.0)


def test_the_warning_travels_with_the_rows() -> None:
    """It is a field of the object, not a note beside it."""
    plan = plan_for(1.0, 1.0)
    assert plan.warning == PROGRESS_SYNC_WARNING
    assert "not the same situation" in plan.model_dump()["warning"]


def test_the_warning_cannot_be_reworded_away() -> None:
    plan = plan_for(1.0, 1.0)
    payload = plan.model_dump()
    payload["warning"] = "the runs are comparable here"

    with pytest.raises(ValidationError, match="may not be reworded"):
        ProgressSyncPlan.model_validate(payload)


def test_two_runs_that_share_no_ground_are_refused() -> None:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    stalled = project([TrackPoint(time=0.0, x=0.0, y=0.0)], line)
    driven = project(straight_track(speed=1.0), line)

    with pytest.raises(ReplaySyncRefusal, match="share no progress"):
        build_progress_sync(stalled, driven, reference=line)


def test_rows_stay_ordered_by_arc_length() -> None:
    plan = plan_for(1.0, 1.0)
    payload = plan.model_dump()
    payload["rows"] = list(reversed(payload["rows"]))

    with pytest.raises(ValidationError, match="ordered by arc length"):
        ProgressSyncPlan.model_validate(payload)


def test_the_degradation_of_the_reference_is_visible_on_the_plan() -> None:
    """A panel reads the quality off the object it is already holding."""
    line = choose_reference(planned_path=None, candidate_path=CORRIDOR)
    plan = build_progress_sync(
        project(straight_track(speed=1.0), line),
        project(straight_track(speed=1.0, offset=0.3), line),
        reference=line,
        steps=11,
    )
    assert plan.reference.quality == "degraded_candidate_path"
    assert plan.reference.is_degraded


# --------------------------------------------------------------------------
# Divergence
# --------------------------------------------------------------------------


def test_a_brief_wobble_is_not_a_divergence() -> None:
    """Two runs weaving in one corridor cross any threshold constantly."""
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    weaving = [
        TrackPoint(time=float(index), x=float(index), y=1.2 if index == 4 else 0.0)
        for index in range(11)
    ]
    plan = build_progress_sync(
        project(straight_track(speed=1.0), line),
        project(weaving, line),
        reference=line,
        steps=41,
    )

    report = find_divergence(plan, threshold_m=0.5, sustain_m=2.0)
    assert report.sustained is None


def test_a_sustained_parting_is_reported_where_it_started() -> None:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    detour = [
        TrackPoint(time=float(index), x=float(index), y=0.0 if index < 4 else 2.0)
        for index in range(11)
    ]
    plan = build_progress_sync(
        project(straight_track(speed=1.0), line),
        project(detour, line),
        reference=line,
        steps=101,
    )

    report = find_divergence(plan, threshold_m=0.5, sustain_m=2.0)
    assert report.sustained is not None
    assert report.sustained.kind == "sustained_cross_track"
    # Not 4.0: the samples are a metre apart, so the run crosses half a
    # metre of offset a quarter of the way into the segment that leaves
    # the line. Reporting the sample index instead would name a place
    # the runs were still together.
    assert report.sustained.progress_m == pytest.approx(3.25, abs=0.15)
    assert report.sustained.separation_m == pytest.approx(0.5, abs=0.25)


def plan_for_detour(*, step_seconds: float) -> ProgressSyncPlan:
    """Candidate B leaves the line at x=4, sampled every ``step_seconds``."""
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    detour = [
        TrackPoint(time=float(index) * step_seconds, x=float(index), y=0.0 if index < 4 else 2.0)
        for index in range(11)
    ]
    return build_progress_sync(
        project(straight_track(speed=1.0), line),
        project(detour, line),
        reference=line,
        steps=101,
    )


def test_the_sustain_window_is_arc_length_so_a_slow_run_is_not_penalised() -> None:
    """A sample-count window would call the slower run divergent for
    driving slowly; arc length holds both to the same standard."""
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    slow_detour = [
        TrackPoint(time=float(index) * 4, x=float(index), y=0.0 if index < 4 else 2.0)
        for index in range(11)
    ]
    plan = build_progress_sync(
        project(straight_track(speed=1.0), line),
        project(slow_detour, line),
        reference=line,
        steps=101,
    )

    fast = find_divergence(plan_for_detour(step_seconds=1.0), threshold_m=0.5, sustain_m=2.0)
    report = find_divergence(plan, threshold_m=0.5, sustain_m=2.0)
    assert report.sustained is not None
    assert fast.sustained is not None
    # Four times slower, same arc length: the same verdict at the same
    # place. A window counted in samples would have moved.
    assert report.sustained.progress_m == pytest.approx(fast.sustained.progress_m)


def test_events_anchor_a_divergence_without_any_detector() -> None:
    plan = plan_for(1.0, 1.0)
    report = find_divergence(
        plan,
        events_a=[(3.0, "replan"), (7.0, "replan")],
        events_b=[(5.0, "stuck"), (2.0, "goal_reached")],
    )

    kinds = {(anchor.event, anchor.side) for anchor in report.anchors}
    assert kinds == {("replan", "a"), ("stuck", "b")}
    # Only the first of a repeated event, and nothing outside the
    # anchor vocabulary.
    assert "goal_reached" not in ANCHOR_EVENTS
    replan = next(anchor for anchor in report.anchors if anchor.event == "replan")
    assert replan.progress_m == pytest.approx(3.0, abs=0.5)


def test_the_earliest_parting_is_the_one_a_reader_is_sent_to() -> None:
    line = ReferenceLine(points=tuple(CORRIDOR), quality="reference_plan")
    detour = [
        TrackPoint(time=float(index), x=float(index), y=0.0 if index < 6 else 2.0)
        for index in range(11)
    ]
    plan = build_progress_sync(
        project(straight_track(speed=1.0), line),
        project(detour, line),
        reference=line,
        steps=101,
    )

    report = find_divergence(plan, threshold_m=0.5, sustain_m=2.0, events_a=[(2.0, "replan")])
    assert report.earliest is not None
    assert report.earliest.kind == "event"
    assert report.earliest.progress_m < report.sustained.progress_m  # type: ignore[union-attr]


def test_a_divergence_must_carry_what_its_kind_promises() -> None:
    from planbench_explanation.replay_sync import DivergencePoint

    with pytest.raises(ValidationError):  # event without naming the event
        DivergencePoint(kind="event", progress_m=1.0, time_a=1.0, time_b=1.0)
    with pytest.raises(ValidationError):  # cross-track without a separation
        DivergencePoint(kind="sustained_cross_track", progress_m=1.0, time_a=1.0, time_b=1.0)


def test_nonsense_windows_are_refused() -> None:
    plan = plan_for(1.0, 1.0)
    with pytest.raises(ReplaySyncRefusal):
        find_divergence(plan, threshold_m=0.0)
    with pytest.raises(ReplaySyncRefusal):
        find_divergence(plan, sustain_m=-1.0)


def test_the_same_inputs_give_the_same_plan() -> None:
    assert plan_for(1.0, 0.5).model_dump() == plan_for(1.0, 0.5).model_dump()


def test_a_sample_cannot_claim_negative_progress() -> None:
    with pytest.raises(ValidationError):
        ProjectedSample(time=0.0, progress_m=-1.0, cross_track_m=0.0)
