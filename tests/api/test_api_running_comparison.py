"""The E4.3 running comparison, where the API feeds it — wiring, not maths.

The metric definitions are tested in ``test_explanation_running_metrics``.
What is left to get wrong is here: which line arc length is measured
along, and whether the number handed to the panel came from that line at
all. A first draft of this wiring fed the metrics *cumulative driven
distance* as progress, which is arithmetically fine and makes
``path_efficiency`` — progress over distance driven — identically 1.0 for
every candidate on every episode. It renders, it reads plausibly, and it
measures nothing. That is what the detour test below exists to catch.
"""

from __future__ import annotations

import pytest

from planbench_api.decision_service import _first_route, _slice_for
from planbench_explanation.replay_sync import ReferenceLine
from planbench_explanation.running_metrics import (
    Deployment,
    RunningMetricsRefusal,
    sample_at,
)

#: Straight down the x axis: every deviation is visible as lost efficiency.
STRAIGHT = ReferenceLine(points=((0.0, 0.0), (10.0, 0.0)), quality="reference_plan")

DEPLOYMENT = Deployment(
    robot_radius_m=0.3,
    control_period_s=0.1,
    clearance_warning_m=0.5,
    max_linear_velocity=1.0,
    reference_length_m=10.0,
)


def payload(points: list[tuple[float, float]], **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "candidate_id": "cand_a",
        "t": [float(index) for index in range(len(points))],
        "x": [x for x, _ in points],
        "y": [y for _, y in points],
        "clearance_m": [0.8] * len(points),
        "planner_latency_ms": [10.0] * len(points),
        "events": [],
    }
    body.update(overrides)
    return body


def route(*points: tuple[float, float]) -> dict[str, object]:
    return {"attempt": 1, "from_index": 0, "points": [{"x": x, "y": y} for x, y in points]}


class TestWhichLineIsTheReference:
    def test_the_first_attempt_that_found_a_path_is_the_reference(self) -> None:
        """One line for the whole episode.

        A later replan's route describes only the part after it, so arc
        length measured along it would restart mid-episode and the two
        candidates would be placed on rungs that are not the same rung.
        """
        first = route((0.0, 0.0), (5.0, 0.0))
        second = {**route((2.0, 0.0), (2.0, 3.0)), "attempt": 2, "from_index": 40}
        assert _first_route({"planned_routes": [first, second]}) == [(0.0, 0.0), (5.0, 0.0)]

    def test_an_opening_refusal_is_skipped_rather_than_taken_as_the_line(self) -> None:
        """A no-path attempt has no polyline; it is not a zero-length plan."""
        refused = {**route(), "points": []}
        found = _first_route({"planned_routes": [refused, route((0.0, 0.0), (5.0, 0.0))]})
        assert found == [(0.0, 0.0), (5.0, 0.0)]

    def test_a_run_that_kept_no_plans_gets_no_reference(self) -> None:
        """Recorded before the E4.5 sidecar. The view then says which lens
        it fell back to, rather than pretending it had the plan."""
        assert _first_route({"planned_routes": []}) is None
        assert _first_route({}) is None

    def test_a_single_point_route_is_not_a_line(self) -> None:
        """``ReferenceLine`` would refuse it; refusing here keeps the
        refusal out of the request path."""
        assert _first_route({"planned_routes": [route((1.0, 1.0))]}) is None


class TestProgressComesFromTheProjection:
    def test_a_detour_costs_path_efficiency(self) -> None:
        """The regression guard for the driven-distance stand-in.

        This robot ends 6 m along the reference having driven 12 m. Any
        implementation that reported progress as distance driven would
        return exactly 1.0 here and would do so for every trace ever
        recorded.
        """
        detour = payload(
            [(0.0, 0.0), (2.0, 0.0), (2.0, 3.0), (4.0, 3.0), (4.0, 0.0), (6.0, 0.0)]
        )
        slice_ = _slice_for(detour, STRAIGHT)

        assert slice_.progress_m[-1] == pytest.approx(6.0)
        sample = sample_at(slice_, len(slice_.t) - 1, deployment=DEPLOYMENT)
        assert sample.path_efficiency == pytest.approx(0.5)

    def test_a_straight_run_scores_one(self) -> None:
        """The other half of the pair, so the test above cannot pass by
        every trace scoring badly."""
        slice_ = _slice_for(payload([(0.0, 0.0), (3.0, 0.0), (6.0, 0.0)]), STRAIGHT)
        sample = sample_at(slice_, 2, deployment=DEPLOYMENT)
        assert sample.path_efficiency == pytest.approx(1.0)

    def test_progress_is_measured_along_the_line_not_from_the_origin(self) -> None:
        """A robot driving parallel to the reference, 3 m off it, has made
        the progress its projection says — not its straight-line distance
        from the start, which would count the offset as work done."""
        slice_ = _slice_for(payload([(0.0, 3.0), (4.0, 3.0)]), STRAIGHT)
        assert slice_.progress_m[-1] == pytest.approx(4.0)

    def test_replans_are_read_off_the_trace_events(self) -> None:
        body = payload(
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
            events=[{"index": 1, "event": "replan"}, {"index": 2, "event": "goal_reached"}],
        )
        assert _slice_for(body, STRAIGHT).replan_indices == (1,)


class TestRefusalsRatherThanWrongRows:
    def test_a_short_column_is_refused_not_indexed_past(self) -> None:
        """The payload is read column by column with ``.get(name, [])``, so
        a trace file missing one arrives here as an empty list. Reading
        ``clearance_m`` at a row chosen from ``t`` would then be an
        ``IndexError`` — or, for a merely shorter column, a reading of a
        different moment of the episode than the one asked for.
        """
        body = payload([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)], clearance_m=[])
        with pytest.raises((RunningMetricsRefusal, ValueError)) as caught:
            _slice_for(body, STRAIGHT)
        assert "disagree in length" in str(caught.value)

    def test_a_trace_with_no_samples_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no samples"):
            _slice_for(payload([]), STRAIGHT)


class TestTheSeriesTheCanvasTilesRead:
    """The tiles index this with a scrubber position (`RunningBlock.by_step`)."""

    def test_one_entry_per_trace_row(self) -> None:
        """An off-by-one here shows one candidate a different instant
        than the pose drawn beside it — and nothing on screen would say
        so, because both numbers are plausible for that episode."""
        from planbench_explanation.running_metrics import sample_series

        body = payload([(0.0, 0.0), (1.0, 0.0), (2.0, 0.5), (3.0, 0.5)])
        series = sample_series(_slice_for(body, STRAIGHT), deployment=DEPLOYMENT)
        assert len(series) == len(body["t"])  # type: ignore[arg-type]

    def test_the_series_agrees_with_the_ladder_at_the_same_row(self) -> None:
        """Two shapes of one computation, not two computations.

        The tile under a canvas and the table above it are read together
        by the same person, and a disagreement between them is the
        failure that would be hardest to explain.
        """
        from planbench_explanation.running_metrics import sample_at, sample_series

        slice_ = _slice_for(payload([(0.0, 0.0), (2.0, 0.0), (2.0, 3.0), (5.0, 3.0)]), STRAIGHT)
        series = sample_series(slice_, deployment=DEPLOYMENT)
        for index in range(len(series)):
            assert sample_at(slice_, index, deployment=DEPLOYMENT) == series[index]
