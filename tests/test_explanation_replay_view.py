"""E2 — turning two served traces into one progress-synced view.

The assembly is where the pairing can quietly break: two payloads look
identical in shape whether or not they describe the same episode, and a
viewer built from mismatched ones is the most convincing wrong picture
the platform could draw.
"""

from __future__ import annotations

from typing import Any

import pytest

from planbench_explanation.replay_sync import ReplaySyncRefusal
from planbench_explanation.replay_view import ReplaySyncView, build_replay_sync_view

MISSIONS = [{"id": "m1", "start": {"x": 0.0, "y": 0.0}, "goal": {"x": 10.0, "y": 0.0}}]


def trace(
    candidate: str,
    *,
    episode: str = "ctx017",
    offset: float = 0.0,
    speed: float = 1.0,
    steps: int = 11,
    events: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "candidate_id": candidate,
        "episode_context_id": episode,
        "t": [index / speed for index in range(steps)],
        "x": [float(index) for index in range(steps)],
        "y": [offset for _ in range(steps)],
        "events": events or [],
        "missions": MISSIONS,
    }
    payload.update(overrides)
    return payload


def test_two_traces_become_one_view_with_the_warning_attached() -> None:
    view = build_replay_sync_view(trace("cand_a"), trace("cand_b", speed=0.5), steps=21)

    assert view.episode_context_id == "ctx017"
    assert "not the same situation" in view.plan.warning
    row = next(row for row in view.plan.rows if row.progress_m == pytest.approx(5.0))
    assert row.time_a == pytest.approx(5.0)
    assert row.time_b == pytest.approx(10.0)


def test_the_view_names_whose_path_became_the_ruler() -> None:
    """Without a planned route the reference is a driven path, and the
    candidate that supplied it has zero offset everywhere."""
    view = build_replay_sync_view(trace("cand_a"), trace("cand_b", offset=1.5))

    assert view.plan.reference.quality == "degraded_candidate_path"
    assert view.reference_source_candidate_id == "cand_a"
    assert all(row.cross_track_a == pytest.approx(0.0) for row in view.plan.rows)


def test_a_planned_route_lifts_the_projection_out_of_degraded() -> None:
    """The argument that will stop saying ``degraded_*`` one day."""
    view = build_replay_sync_view(
        trace("cand_a", offset=0.5),
        trace("cand_b", offset=-0.5),
        planned_path=[(0.0, 0.0), (10.0, 0.0)],
    )

    assert view.plan.reference.quality == "reference_plan"
    assert view.reference_source_candidate_id is None
    assert not view.plan.reference.is_degraded


def test_a_view_may_not_claim_a_ruler_it_does_not_have() -> None:
    view = build_replay_sync_view(
        trace("cand_a"), trace("cand_b"), planned_path=[(0.0, 0.0), (10.0, 0.0)]
    )
    payload = view.model_dump()
    payload["reference_source_candidate_id"] = "cand_a"

    with pytest.raises(Exception, match="only a candidate-path reference"):
        ReplaySyncView.model_validate(payload)


def test_traces_from_two_different_episodes_are_refused() -> None:
    """Two panels side by side claim a paired comparison (HĐ-3.2)."""
    with pytest.raises(ReplaySyncRefusal, match="different episodes"):
        build_replay_sync_view(trace("cand_a"), trace("cand_b", episode="ctx018"))


def test_one_candidate_against_itself_is_refused() -> None:
    with pytest.raises(Exception, match="itself"):
        build_replay_sync_view(trace("cand_a"), trace("cand_a", offset=1.0))


def test_ragged_columns_are_refused_rather_than_zipped_short() -> None:
    """A timestamp paired with somebody else's pose places the robot
    somewhere it never was."""
    broken = trace("cand_b")
    broken["y"] = broken["y"][:-3]

    with pytest.raises(ReplaySyncRefusal, match="columns disagree"):
        build_replay_sync_view(trace("cand_a"), broken)


def test_an_empty_trace_is_refused() -> None:
    empty = trace("cand_b")
    empty.update({"t": [], "x": [], "y": []})

    with pytest.raises(ReplaySyncRefusal, match="no samples"):
        build_replay_sync_view(trace("cand_a"), empty)


def test_events_become_anchors_at_the_time_they_fired() -> None:
    view = build_replay_sync_view(
        trace("cand_a", events=[{"index": 3, "event": "replan"}]),
        trace("cand_b", offset=0.2, events=[{"index": 6, "event": "stuck"}]),
    )

    anchors = {(anchor.event, anchor.side) for anchor in view.divergence.anchors}
    assert anchors == {("replan", "a"), ("stuck", "b")}
    replan = next(a for a in view.divergence.anchors if a.event == "replan")
    assert replan.progress_m == pytest.approx(3.0, abs=0.2)


def test_an_event_indexing_nowhere_is_dropped_not_guessed() -> None:
    view = build_replay_sync_view(
        trace(
            "cand_a",
            events=[{"index": 99, "event": "replan"}, {"index": None, "event": "stuck"}],
        ),
        trace("cand_b", offset=0.2),
    )
    assert view.divergence.anchors == ()


def test_without_missions_a_straight_line_is_still_available() -> None:
    """Only when there is no driven path either — which is the case a
    trace with a single repeated pose produces."""
    stalled = trace("cand_a", steps=4)
    stalled["x"] = [2.0, 2.0, 2.0, 2.0]
    stalled["y"] = [3.0, 3.0, 3.0, 3.0]

    view = build_replay_sync_view(stalled, trace("cand_b"))
    assert view.plan.reference.quality == "degraded_straight_line"
    assert view.reference_source_candidate_id is None


def test_the_same_traces_give_the_same_view() -> None:
    first = build_replay_sync_view(trace("cand_a"), trace("cand_b", speed=0.5))
    second = build_replay_sync_view(trace("cand_a"), trace("cand_b", speed=0.5))
    assert first.model_dump() == second.model_dump()
