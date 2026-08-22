"""E3 — detectors describe behaviour and stop there.

Two things every test here is really about: a detector fires on the
pattern it names and on nothing else, and it never reaches for a cause.
"Stopped four times in this stretch" is checkable against the replay;
"got stuck in a local minimum" is a hypothesis, and hypotheses enter the
pipeline much further downstream, through gates this layer is upstream
of.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_explanation.detectors import (
    KNOWN_DETECTIONS,
    ArcWindow,
    Detection,
    DetectorRefusal,
    DetectorSettings,
    Observation,
    detect_all,
    read_trace,
    summarise,
)
from planbench_explanation.replay_sync import ReferenceLine

CORRIDOR = ReferenceLine(points=((0.0, 0.0), (20.0, 0.0)), quality="reference_plan")
SETTINGS = DetectorSettings()


def trace(
    *,
    xs: list[float],
    ys: list[float] | None = None,
    times: list[float] | None = None,
    clearance: list[float] | None = None,
    latency: list[float] | None = None,
    events: list[dict[str, object]] | None = None,
    candidate: str = "cand_a",
) -> dict[str, object]:
    count = len(xs)
    return {
        "candidate_id": candidate,
        "episode_context_id": "ep00",
        "t": times if times is not None else [float(index) for index in range(count)],
        "x": xs,
        "y": ys if ys is not None else [0.0] * count,
        "clearance_m": clearance if clearance is not None else [0.5] * count,
        "planner_latency_ms": latency if latency is not None else [10.0] * count,
        "events": events or [],
    }


def kinds(detections) -> set[str]:  # type: ignore[no-untyped-def]
    return {item.type for item in detections}


def only(detections, kind: str):  # type: ignore[no-untyped-def]
    (found,) = [item for item in detections if item.type == kind]
    return found


# --------------------------------------------------------------------------
# Reading the trace
# --------------------------------------------------------------------------


def test_a_ragged_trace_is_refused_rather_than_zipped_short() -> None:
    payload = trace(xs=[0.0, 1.0, 2.0])
    payload["y"] = [0.0]

    with pytest.raises(DetectorRefusal, match="columns disagree"):
        read_trace(payload)


def test_an_empty_trace_shows_nothing() -> None:
    with pytest.raises(DetectorRefusal):
        read_trace(trace(xs=[]))


def test_events_indexing_nowhere_are_dropped() -> None:
    view = read_trace(
        trace(
            xs=[0.0, 1.0],
            events=[{"index": 99, "event": "replan"}, {"index": 0, "event": "replan"}],
        )
    )
    assert view.events == ((0.0, "replan"),)


# --------------------------------------------------------------------------
# One detector at a time
# --------------------------------------------------------------------------


def test_a_straight_run_along_the_route_sets_off_nothing() -> None:
    """The property that makes the rest worth having.

    A detector that fires on ordinary driving fills the packet with
    noise, and an analyst reading thirty detections an episode learns
    nothing from any of them.
    """
    view = read_trace(trace(xs=[float(index) for index in range(21)]))
    assert detect_all(view, reference=CORRIDOR) == ()


def test_a_route_much_longer_than_the_reference_is_a_detour() -> None:
    # Out along the corridor and back up a side aisle: 20 m of route
    # driven as 30 m.
    xs = [float(index) for index in range(21)]
    ys = [0.0] * 21
    xs += [20.0] * 5
    ys += [float(step) for step in range(1, 6)]
    xs += [20.0] * 5
    ys += [5.0 - float(step) for step in range(1, 6)]
    view = read_trace(trace(xs=xs, ys=ys, times=[float(i) for i in range(len(xs))]))

    detour = only(detect_all(view, reference=CORRIDOR), "detour")

    assert detour.measurements["extra_distance_m"] == pytest.approx(10.0, abs=0.5)
    # The reference's quality travels with the window: "14 m along the
    # route" means something else when the route is a guess.
    assert detour.window is not None
    assert detour.window.projection_quality == "reference_plan"


def test_repeated_long_stops_in_one_stretch_are_a_cluster() -> None:
    # Drives, stops for 3 s, drives, stops for 3 s — one cluster.
    xs = [0.0, 1.0, 2.0, 2.0, 2.0, 2.0, 3.0, 4.0, 4.0, 4.0, 4.0, 5.0]
    view = read_trace(trace(xs=xs))

    cluster = only(detect_all(view, reference=CORRIDOR), "stuck_cluster")

    assert cluster.measurements["stops"] == 2
    assert cluster.measurements["stopped_seconds"] >= 6.0
    assert cluster.window is not None
    assert cluster.window.start_m == pytest.approx(2.0, abs=0.5)


def test_one_brief_pause_is_traffic_not_a_symptom() -> None:
    xs = [0.0, 1.0, 2.0, 2.0, 3.0, 4.0]  # a single 1-sample stop
    view = read_trace(trace(xs=xs, times=[0.0, 1.0, 2.0, 2.5, 3.5, 4.5]))

    assert "stuck_cluster" not in kinds(detect_all(view, reference=CORRIDOR))


def test_several_samples_inside_the_near_miss_band_cluster() -> None:
    xs = [float(index) for index in range(10)]
    clearance = [0.5, 0.5, 0.1, 0.08, 0.12, 0.5, 0.5, 0.5, 0.5, 0.5]
    view = read_trace(trace(xs=xs, clearance=clearance))

    near_miss = only(detect_all(view, reference=CORRIDOR), "near_miss_cluster")

    assert near_miss.measurements["samples"] == 3
    assert near_miss.measurements["min_clearance_m"] == pytest.approx(0.08)


def test_two_close_calls_are_not_a_cluster() -> None:
    clearance = [0.5, 0.1, 0.1, 0.5, 0.5]
    view = read_trace(trace(xs=[0.0, 1.0, 2.0, 3.0, 4.0], clearance=clearance))

    assert "near_miss_cluster" not in kinds(detect_all(view, reference=CORRIDOR))


def test_replans_bunched_into_one_window_are_a_storm() -> None:
    events = [{"index": index, "event": "replan"} for index in (2, 3, 5)]
    view = read_trace(trace(xs=[float(i) for i in range(12)], events=events))

    storm = only(detect_all(view, reference=CORRIDOR), "replan_storm")

    assert storm.measurements["replans"] == 3


def test_replans_spread_across_the_run_are_not_a_storm() -> None:
    events = [{"index": index, "event": "replan"} for index in (0, 15, 30)]
    xs = [float(index) for index in range(31)]
    view = read_trace(trace(xs=xs, events=events))

    assert "replan_storm" not in kinds(detect_all(view, reference=CORRIDOR))


def test_driving_back_and_forth_is_oscillation() -> None:
    xs = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    view = read_trace(trace(xs=xs))

    oscillation = only(detect_all(view, reference=CORRIDOR), "oscillation")

    assert oscillation.measurements["reversals"] >= 4


def test_a_long_control_tick_is_a_spike() -> None:
    latency = [10.0, 12.0, 140.0, 11.0, 10.0]
    view = read_trace(trace(xs=[0.0, 1.0, 2.0, 3.0, 4.0], latency=latency))

    spike = only(detect_all(view, reference=CORRIDOR), "latency_spike")

    assert spike.measurements["peak_latency_ms"] == pytest.approx(140.0)


def test_a_spike_is_an_absolute_threshold_not_this_episodes_worst_tick() -> None:
    """A percentile always finds a "spike", even in a healthy run."""
    view = read_trace(trace(xs=[0.0, 1.0, 2.0], latency=[8.0, 9.0, 12.0]))

    assert "latency_spike" not in kinds(detect_all(view, reference=CORRIDOR))


# --------------------------------------------------------------------------
# The one that needs the map
# --------------------------------------------------------------------------


def test_a_refusal_beside_a_gap_too_narrow_is_reported_as_both_facts() -> None:
    view = read_trace(trace(xs=[0.0, 1.0], events=[{"index": 1, "event": "no_path"}]))

    refusal = only(
        detect_all(
            view,
            reference=CORRIDOR,
            narrowest_passage_m=0.68,
            required_passage_width_m=0.74,
        ),
        "narrow_gap_refusal",
    )

    assert refusal.measurements["margin_m"] == pytest.approx(-0.06)
    # No location: a refusal to plan happens at a pose, not along a stretch.
    assert refusal.window is None


def test_without_the_map_feature_it_does_not_run_rather_than_guess() -> None:
    view = read_trace(trace(xs=[0.0, 1.0], events=[{"index": 1, "event": "no_path"}]))

    assert "narrow_gap_refusal" not in kinds(detect_all(view, reference=CORRIDOR))
    assert "narrow_gap_refusal" not in kinds(
        detect_all(view, reference=CORRIDOR, narrowest_passage_m=0.68)
    )


def test_a_refusal_where_the_route_was_wide_enough_is_not_this_pattern() -> None:
    view = read_trace(trace(xs=[0.0, 1.0], events=[{"index": 1, "event": "no_path"}]))

    assert "narrow_gap_refusal" not in kinds(
        detect_all(
            view, reference=CORRIDOR, narrowest_passage_m=1.20, required_passage_width_m=0.74
        )
    )


# --------------------------------------------------------------------------
# Prevalence
# --------------------------------------------------------------------------


def detection(episode: str, **measurements: float) -> Detection:
    return Detection(
        type="detour",
        candidate_id="cand_a",
        episode_context_id=episode,
        measurements=measurements,
    )


def test_prevalence_counts_episodes_looked_at_not_episodes_that_fired() -> None:
    """One detour in thirty is an anecdote; twenty-seven is a property.

    Counting the denominator from the detections themselves would make
    every pattern universal.
    """
    observations = summarise(
        [detection("ep00", extra_distance_m=9.0), detection("ep01", extra_distance_m=11.0)],
        episodes_total=30,
    )

    (observation,) = observations
    assert observation.episodes_seen == 2
    assert observation.episodes_total == 30
    assert observation.prevalence == pytest.approx(2 / 30)


def test_the_typical_number_is_a_median_not_a_mean() -> None:
    """One runaway episode must not set the number a reader takes as typical."""
    observations = summarise(
        [
            detection("ep00", extra_distance_m=2.0),
            detection("ep01", extra_distance_m=3.0),
            detection("ep02", extra_distance_m=95.0),
        ],
        episodes_total=3,
    )

    assert observations[0].typical["extra_distance_m"] == pytest.approx(3.0)
    assert observations[0].worst_episode_context_id == "ep02"


def test_two_detections_in_one_episode_are_one_episode() -> None:
    observations = summarise(
        [detection("ep00", extra_distance_m=2.0), detection("ep00", extra_distance_m=4.0)],
        episodes_total=10,
    )
    assert observations[0].episodes_seen == 1


def test_a_pattern_cannot_appear_in_more_episodes_than_were_run() -> None:
    with pytest.raises(ValidationError):
        Observation(type="detour", candidate_id="cand_a", episodes_seen=31, episodes_total=30)


def test_a_denominator_of_zero_is_refused() -> None:
    with pytest.raises(DetectorRefusal):
        summarise([], episodes_total=0)


def test_a_window_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(ValidationError):
        ArcWindow(
            start_m=5.0, end_m=1.0, start_s=0.0, end_s=1.0, projection_quality="reference_plan"
        )


def test_the_settings_are_readable_and_changeable() -> None:
    """Thresholds a person can calibrate, not literals buried in code."""
    view = read_trace(trace(xs=[0.0, 1.0, 2.0], latency=[8.0, 9.0, 12.0]))

    sensitive = DetectorSettings(latency_spike_ms=10.0)
    assert "latency_spike" in kinds(detect_all(view, reference=CORRIDOR, settings=sensitive))


def near_miss(episode: str, clearance: float, samples: float = 3.0) -> Detection:
    return Detection(
        type="near_miss_cluster",
        candidate_id="cand_a",
        episode_context_id=episode,
        measurements={"min_clearance_m": clearance, "samples": samples},
    )


def test_the_worst_episode_is_the_dangerous_one_not_the_alphabetical_one() -> None:
    """Clearance is worse when it is *smaller*.

    An earlier version took the first measurement key alphabetically —
    ``min_clearance_m`` — and called the largest value the worst, which
    named the safest episode as the one to watch: 0.14 m over 0.01 m.
    """
    observations = summarise(
        [near_miss("ep_safe", 0.14), near_miss("ep_danger", 0.01)], episodes_total=2
    )

    assert observations[0].worst_episode_context_id == "ep_danger"


def test_each_detection_type_says_which_direction_is_worse() -> None:
    """Every other measurement here is worse when it is larger."""
    from planbench_explanation.detectors import SEVERITY

    assert set(SEVERITY) == set(KNOWN_DETECTIONS)
    assert SEVERITY["near_miss_cluster"][1] == "lower"
    assert SEVERITY["narrow_gap_refusal"][1] == "lower"
    assert SEVERITY["latency_spike"][1] == "higher"


def test_one_busy_episode_does_not_outvote_three_quiet_ones() -> None:
    """The median is over *episodes that fired*, as the docstring says.

    Letting every cluster into it weights an episode that produced four
    of them four times, and the number a reader takes as typical then
    describes one episode.
    """
    detections = [near_miss("ep_busy", 0.02) for _ in range(4)]
    detections += [near_miss("ep_a", 0.30), near_miss("ep_b", 0.32), near_miss("ep_c", 0.34)]

    (observation,) = summarise(detections, episodes_total=4)

    assert observation.episodes_seen == 4
    # Four episodes, medians of (0.02, 0.30, 0.32, 0.34) → 0.31. Counting
    # detections instead would have put the median down among the busy
    # episode's four rows.
    assert observation.typical["min_clearance_m"] == pytest.approx(0.31)
    assert observation.worst_episode_context_id == "ep_busy"


def test_an_episode_is_summarised_by_its_worst_detection() -> None:
    observations = summarise([near_miss("ep00", 0.25), near_miss("ep00", 0.04)], episodes_total=1)
    assert observations[0].typical["min_clearance_m"] == pytest.approx(0.04)


def test_contact_is_the_worst_case_not_a_missing_measurement() -> None:
    """Zero is falsy, and that lost the ranking to a safer episode.

    ``severity_of(item) or -math.inf`` turned a near miss of **0.00 m**
    — contact — into negative infinity, so a 0.10 m episode was reported
    as the one to watch.
    """
    observations = summarise(
        [near_miss("ep_contact", 0.0), near_miss("ep_near", 0.1)], episodes_total=2
    )

    assert observations[0].worst_episode_context_id == "ep_contact"


def test_a_detection_with_no_severity_measurement_sorts_last() -> None:
    """ "No number" and "the worst number" must not be the same thing."""
    silent = Detection(
        type="near_miss_cluster",
        candidate_id="cand_a",
        episode_context_id="ep_silent",
        measurements={"samples": 3.0},
    )

    observations = summarise([silent, near_miss("ep_contact", 0.0)], episodes_total=2)

    assert observations[0].worst_episode_context_id == "ep_contact"
