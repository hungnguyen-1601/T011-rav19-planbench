"""Explaining one episode, without inventing anything the file cannot say.

Two things have to hold, and only one of them is visible without tests.

The advice must be true of the file. The fixtures below are the twelve
real traces of the stored `demo_hall` run — three `astar+dwa` episodes
that ended `stuck` and nine that reached the goal — and the numbers
asserted against them (the robot stopped at t = 11.40 s, 9.55 s before
the file ended, having swept 1.92 rad on the spot) are read off the
Parquet, not chosen.

And every citation has to resolve. An unresolvable ``field_path`` is
dropped by ``keep_resolvable`` **silently**, so a typo looks exactly like
a rule that decided not to fire — the module would go on returning
plausible advice with one rule permanently dead. So the coverage test
here is not "some advice came back": it is that every code in
``TRACE_REVIEW_CODES`` is emitted by some fixture, which is the only way
a dropped citation shows up as a failure.

Six of the eleven rules cannot be exercised by the stored run: nothing in
it collided, timed out, failed to find a path, replanned, exceeded its
sample period, or stopped without a verdict. Those use frames built here
row by row — synthetic, and said so.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from planbench_decision.advice import Advice, keep_resolvable
from planbench_decision.self_check import exists
from planbench_metrics.trace_review import (
    TRACE_REVIEW_CODES,
    summarise_trace,
    trace_advice,
)

TRACES = Path(__file__).resolve().parent.parent / "artifacts/traces"

#: The `astar+dwa` candidate of the stored run, whose episodes on these
#: three contexts ended `stuck`, and the `rrtstar+dwa` one that cleared
#: every gate. Named rather than globbed so a test that stops finding
#: them fails instead of quietly asserting over nothing.
STUCK = ("60c8e26fe591", "2274d4058101")
REACHED = ("db26440f6052", "2274d4058101")

DT = 0.05


# --------------------------------------------------------------------
# Real stored traces.
# --------------------------------------------------------------------


def load(candidate_id: str, episode_context_id: str) -> dict[str, Any]:
    """Summarise one stored trace, ids taken from its Parquet footer."""
    path = TRACES / candidate_id / f"{episode_context_id}.parquet"
    if not path.exists():
        pytest.skip(f"stored trace {path} not present in this checkout")
    table = pq.read_table(path)
    meta = json.loads((table.schema.metadata or {})[b"planbench_trace"])
    return summarise_trace(
        table.to_pandas(),
        candidate_id=meta["candidate_id"],
        episode_context_id=meta["episode_context_id"],
    )


def stored_summaries() -> list[dict[str, Any]]:
    if not TRACES.exists():
        pytest.skip("stored traces not present in this checkout")
    found = []
    for path in sorted(TRACES.rglob("*.parquet")):
        found.append(load(path.parent.name, path.stem))
    if not found:
        pytest.skip("stored traces not present in this checkout")
    return found


@pytest.fixture
def stuck() -> dict[str, Any]:
    return load(*STUCK)


@pytest.fixture
def reached() -> dict[str, Any]:
    return load(*REACHED)


# --------------------------------------------------------------------
# Frames built here, for the six outcomes the stored run never produced.
# --------------------------------------------------------------------


def _series(value: float | Sequence[float], rows: int) -> np.ndarray:
    if isinstance(value, (int, float)):
        return np.full(rows, float(value))
    array = np.asarray(value, dtype=float)
    assert array.size == rows, "fixture series must match the row count"
    return array


def frame(
    *,
    rows: int = 100,
    v: float | Sequence[float] = 0.5,
    omega: float | Sequence[float] = 0.0,
    clearance: float | Sequence[float] = 1.0,
    latency: float | Sequence[float] = 3.0,
    events: Mapping[int, str] | None = None,
) -> pd.DataFrame:
    """A trace-shaped frame with all nine HĐ-5 columns.

    Pose is integrated from the velocities rather than passed in, so a
    frame cannot claim the robot stood still and moved at the same time —
    which is exactly the contradiction the progress rules read.
    """
    speed = _series(v, rows)
    turn = _series(omega, rows)
    theta = np.cumsum(turn) * DT
    x = np.cumsum(speed * np.cos(theta)) * DT
    y = np.cumsum(speed * np.sin(theta)) * DT
    column = [None] * rows
    for index, name in (events or {}).items():
        column[index] = name
    return pd.DataFrame(
        {
            "t": np.arange(rows) * DT,
            "x": x,
            "y": y,
            "theta": theta,
            "v": speed,
            "omega": turn,
            "clearance_m": _series(clearance, rows),
            "planner_latency_ms": _series(latency, rows),
            "event": column,
        }
    )


def collided() -> pd.DataFrame:
    """Driving straight into something: the margin goes in the last 2 s."""
    return frame(
        rows=100,
        clearance=np.concatenate([np.full(40, 1.5), np.linspace(1.5, 0.0, 60)]),
        events={99: "collision"},
    )


def no_path() -> pd.DataFrame:
    return frame(rows=20, v=0.0, events={19: "no_path"})


def timed_out() -> pd.DataFrame:
    return frame(rows=100, v=0.4, events={99: "timeout"})


def replanned() -> pd.DataFrame:
    latency = np.full(100, 3.0)
    latency[30] = 210.0
    latency[70] = 180.0
    return frame(rows=100, latency=latency, events={30: "replan", 70: "replan", 99: "timeout"})


def slow_planner() -> pd.DataFrame:
    """Planning takes 80 ms on a file recorded every 50 ms."""
    return frame(rows=100, latency=80.0, events={99: "goal_reached"})


def cut_short() -> pd.DataFrame:
    """A file that just stops. No terminal event on the last row."""
    return frame(rows=100)


def synthetic_summaries() -> dict[str, dict[str, Any]]:
    return {
        name: summarise_trace(builder(), candidate_id="cand", episode_context_id=name)
        for name, builder in (
            ("collided", collided),
            ("no_path", no_path),
            ("timed_out", timed_out),
            ("replanned", replanned),
            ("slow_planner", slow_planner),
            ("cut_short", cut_short),
        )
    }


def codes(items: tuple[Advice, ...]) -> set[str]:
    return {item.code for item in items}


# --------------------------------------------------------------------


class TestItReadsTheRealStuckEpisode:
    """`astar+dwa` on context 2274d4058101. It stopped and span."""

    def test_the_terminal_event_is_read_from_the_file(self, stuck: dict[str, Any]) -> None:
        assert stuck["episode"]["terminal_event"] == "stuck"
        assert stuck["episode"]["rows"] == 420
        assert stuck["episode"]["event_counts"]["stuck"] == 1

    def test_it_finds_where_the_episode_actually_ended(self, stuck: dict[str, Any]) -> None:
        """The terminal row is t = 20.95 s; the robot's last movement is
        at 11.40 s. Nine and a half seconds of the file are the clock."""
        assert stuck["progress"]["last_motion_t"] == pytest.approx(11.40, abs=1e-6)
        assert stuck["progress"]["stalled_s"] == pytest.approx(9.55, abs=1e-6)
        assert stuck["episode"]["t_end"] == pytest.approx(20.95, abs=1e-6)

    def test_the_stall_is_reported_as_blocking(self, stuck: dict[str, Any]) -> None:
        found = next(a for a in trace_advice(stuck) if a.code == "TR_STALLED_BEFORE_END")
        assert found.severity == "blocking"
        assert "11.40" in found.claim
        assert "9.55" in found.ground

    def test_a_spin_is_told_apart_from_a_freeze(self, stuck: dict[str, Any]) -> None:
        """It was not wedged and still — it swept 1.92 rad on the spot at
        0.2 rad/s, which is a controller still issuing commands."""
        assert stuck["progress"]["heading_swept_after_stall_rad"] == pytest.approx(1.915, abs=1e-3)
        assert stuck["progress"]["turn_rate_after_stall_rad_per_s"] == pytest.approx(0.20, abs=0.01)
        assert "TR_SPINNING_IN_PLACE" in codes(trace_advice(stuck))

    def test_the_stall_is_not_counted_as_oscillation(self, stuck: dict[str, Any]) -> None:
        """Every reversal happened while driving; the still tail would
        halve the rate and describe the stall instead of the controller."""
        assert stuck["oscillation"]["sign_changes"] == 17
        assert stuck["oscillation"]["sign_changes_driving"] == 17
        assert stuck["oscillation"]["per_second"] == pytest.approx(0.811, abs=1e-3)
        assert stuck["oscillation"]["per_second_driving"] == pytest.approx(1.491, abs=1e-3)

    def test_the_subject_names_the_candidate_and_the_episode(self, stuck: dict[str, Any]) -> None:
        for item in trace_advice(stuck):
            assert item.subject == "60c8e26fe591/2274d4058101"


class TestItDoesNotInventProblems:
    def test_a_successful_episode_draws_no_blocking_advice(self, reached: dict[str, Any]) -> None:
        assert reached["episode"]["terminal_event"] == "goal_reached"
        for item in trace_advice(reached):
            assert item.severity != "blocking", item.code

    def test_every_stored_episode_that_reached_its_goal_is_left_alone(self) -> None:
        for summary in stored_summaries():
            if summary["episode"]["terminal_event"] != "goal_reached":
                continue
            assert not [a for a in trace_advice(summary) if a.severity == "blocking"]

    def test_a_clean_arrival_is_not_read_as_a_stall(self) -> None:
        """A robot that decelerates onto its goal stands still at the end
        of its file too. Reporting that as a stall would turn every tidy
        arrival into a blocking finding."""
        stopped = frame(
            rows=100,
            v=np.concatenate([np.full(40, 0.5), np.zeros(60)]),
            events={99: "goal_reached"},
        )
        summary = summarise_trace(stopped)
        assert summary["progress"]["stalled_s"] == pytest.approx(3.0, abs=1e-6)
        assert "TR_STALLED_BEFORE_END" not in codes(trace_advice(summary))

    def test_the_oscillation_rule_is_a_symptom_and_says_so(self) -> None:
        """One stored episode that *reached its goal* crosses the same
        reversal rate as the stuck ones. The rule is therefore material,
        never blocking — a threshold that separates nothing must not
        decide anything."""
        crossing = [
            summary
            for summary in stored_summaries()
            if summary["episode"]["terminal_event"] == "goal_reached"
            and "TR_OSCILLATING" in codes(trace_advice(summary))
        ]
        assert crossing, "expected the known crossing episode in the stored run"
        for summary in crossing:
            found = next(a for a in trace_advice(summary) if a.code == "TR_OSCILLATING")
            assert found.severity == "material"


class TestTheOutcomesTheStoredRunNeverProduced:
    def test_a_collision_is_named_and_the_approach_measured(self) -> None:
        summary = summarise_trace(collided())
        found = next(a for a in trace_advice(summary) if a.code == "TR_COLLISION")
        assert found.severity == "blocking"
        assert summary["clearance"]["min_m"] == pytest.approx(0.0, abs=1e-9)
        assert summary["clearance"]["approach_rate_m_per_s"] > 0

    def test_a_collapsing_margin_is_a_separate_finding(self) -> None:
        """ "It hit something" and "it drove into it at 0.3 m/s having
        given away 90% of its margin in two seconds" are one event and
        two different things to do about it."""
        summary = summarise_trace(collided())
        assert summary["clearance"]["last_is_minimum"] is True
        assert summary["clearance"]["collapse_fraction"] > 0.5
        assert {"TR_COLLISION", "TR_CLEARANCE_COLLAPSE"} <= codes(trace_advice(summary))

    def test_a_no_path_episode_says_nothing_downstream_ran(self) -> None:
        found = next(a for a in trace_advice(summarise_trace(no_path())) if a.code == "TR_NO_PATH")
        assert found.severity == "blocking"
        assert "controller" in found.ground

    def test_a_timeout_while_still_driving_is_not_a_stall(self) -> None:
        summary = summarise_trace(timed_out())
        assert summary["progress"]["stalled_s"] == pytest.approx(0.0, abs=1e-9)
        found = codes(trace_advice(summary))
        assert "TR_TIMEOUT_STILL_DRIVING" in found
        assert "TR_STALLED_BEFORE_END" not in found

    def test_replans_are_counted_and_priced(self) -> None:
        summary = summarise_trace(replanned())
        assert summary["replan"]["count"] == 2
        assert summary["replan"]["times"] == pytest.approx([1.5, 3.5])
        assert summary["replan"]["max_at_replan_ms"] == pytest.approx(210.0)
        assert summary["replan"]["median_elsewhere_ms"] == pytest.approx(3.0)
        assert summary["replan"]["extra_ms"] == pytest.approx(207.0)
        assert "TR_REPLAN_COST" in codes(trace_advice(summary))

    def test_a_planner_slower_than_its_own_sample_period(self) -> None:
        summary = summarise_trace(slow_planner())
        assert summary["latency"]["sample_period_ms"] == pytest.approx(50.0)
        assert summary["latency"]["p99_over_sample_period"] == pytest.approx(1.6)
        assert summary["latency"]["steps_over_sample_period"] == 100
        found = next(a for a in trace_advice(summary) if a.code == "TR_LATENCY_OVER_SAMPLE_PERIOD")
        assert "G4" in found.ground, "must hand the deadline question back to the gate"

    def test_a_file_that_stops_without_a_verdict(self) -> None:
        summary = summarise_trace(cut_short())
        assert summary["episode"]["terminal_event"] is None
        found = next(a for a in trace_advice(summary) if a.code == "TR_NO_TERMINAL_EVENT")
        assert found.severity == "material"


class TestEveryCitationResolves:
    """The one test that catches a dead rule.

    ``keep_resolvable`` drops an unresolvable path without a word, so a
    mistyped citation is indistinguishable from a rule that chose not to
    fire. Asserting resolution on whatever came back is not enough — a
    dropped rule returns nothing to assert on. Coverage of every declared
    code is what makes the drop visible.
    """

    def test_against_every_stored_trace(self) -> None:
        for summary in stored_summaries():
            for item in trace_advice(summary):
                assert exists(summary, item.field_path), f"{item.code} cites {item.field_path}"

    def test_against_every_synthetic_frame(self) -> None:
        for name, summary in synthetic_summaries().items():
            for item in trace_advice(summary):
                assert exists(summary, item.field_path), f"{name}: {item.code}"

    def test_every_declared_code_is_reachable(self) -> None:
        emitted: set[str] = set()
        for summary in [*stored_summaries(), *synthetic_summaries().values()]:
            emitted |= codes(trace_advice(summary))
        assert emitted == set(TRACE_REVIEW_CODES)

    def test_a_null_field_is_still_a_citable_field(self) -> None:
        """``resolve()`` cannot tell "absent" from "present and null", and
        ``TR_NO_TERMINAL_EVENT`` exists precisely to point at a null. It
        survives only because ``keep_resolvable`` tests presence."""
        summary = summarise_trace(cut_short())
        assert summary["episode"]["terminal_event"] is None
        assert exists(summary, "episode.terminal_event")
        assert "TR_NO_TERMINAL_EVENT" in codes(trace_advice(summary))

    def test_a_mistyped_path_would_vanish_without_a_word(self) -> None:
        """The failure mode the coverage test above exists to catch."""
        summary = summarise_trace(cut_short())
        typo = Advice(
            code="TR_TYPO",
            kind="diagnosis",
            severity="blocking",
            claim="x",
            ground="y",
            field_path="progress.stalled_seconds",
            do="z",
        )
        assert keep_resolvable((typo,), summary) == ()

    def test_no_rule_cites_a_key_the_summary_does_not_declare(self) -> None:
        """Every section is present for every frame, including one with
        no usable columns at all — so a citation cannot depend on which
        episode happened to be loaded."""
        bare = summarise_trace(pd.DataFrame({"t": [0.0]}))
        for section in ("episode", "clearance", "oscillation", "progress", "replan", "latency"):
            assert section in bare
        full = summarise_trace(cut_short())
        for section, values in full.items():
            assert set(bare[section]) == set(values), section


class TestItNamesTheBarredMove:
    def test_every_blocking_advice_names_one(self) -> None:
        for summary in [*stored_summaries(), *synthetic_summaries().values()]:
            for item in trace_advice(summary):
                if item.severity == "blocking":
                    assert item.do_not, item.code

    def test_the_time_limit_edit_is_named_where_it_would_hide_a_stall(
        self, stuck: dict[str, Any]
    ) -> None:
        """A robot that stopped 9.55 s before the file ended does not need
        a longer episode, and a longer episode is one form field away."""
        found = next(a for a in trace_advice(stuck) if a.code == "TR_STALLED_BEFORE_END")
        assert "time limit" in found.do_not

    def test_the_latency_sample_edit_is_named(self) -> None:
        found = next(
            a for a in trace_advice(summarise_trace(replanned())) if a.code == "TR_REPLAN_COST"
        )
        assert "p99" in found.do_not

    def test_a_disclosure_refuses_to_judge_a_clearance_it_cannot(
        self, reached: dict[str, Any]
    ) -> None:
        """The trace has no near-miss threshold in it. Calling 5 cm a near
        miss from this file would be a threshold nobody declared."""
        found = next(a for a in trace_advice(reached) if a.code == "TR_MARGIN_SPENT")
        assert found.severity == "disclosure"
        assert "near miss" in found.do_not
        assert "task profile" in found.ground or "deployment" in found.ground


class TestItNeverBreaks:
    def test_an_empty_summary_returns_nothing(self) -> None:
        assert trace_advice({}) == ()

    def test_a_malformed_summary_returns_nothing_rather_than_raising(self) -> None:
        assert trace_advice({"episode": "not a dict"}) == ()
        assert trace_advice({"progress": {"stalled_s": "soon"}}) == ()
        assert trace_advice({"episode": {"event_counts": {"collision": "many"}}}) == ()

    def test_an_empty_frame_summarises_to_nulls(self) -> None:
        summary = summarise_trace(pd.DataFrame({"t": []}))
        assert summary["episode"]["rows"] == 0
        assert summary["clearance"]["min_m"] is None
        assert trace_advice(summary) == ()

    def test_a_frame_missing_columns_still_summarises(self) -> None:
        summary = summarise_trace(pd.DataFrame({"t": [0.0, 0.05, 0.10]}))
        assert summary["episode"]["sample_period_s"] == pytest.approx(0.05)
        assert summary["progress"]["path_length_m"] is None
        assert summary["oscillation"]["per_second"] is None
        assert trace_advice(summary) == ()

    def test_a_missing_event_column_is_not_a_cut_short_episode(self) -> None:
        """Both leave ``terminal_event`` null, and only one of them is an
        episode that stopped without a verdict. Firing on the other would
        be inventing an outcome out of a column nobody wrote."""
        absent = summarise_trace(pd.DataFrame({"t": [0.0, 0.05], "v": [0.5, 0.5]}))
        assert absent["episode"]["event_column"] is False
        assert absent["episode"]["terminal_event"] is None
        assert "TR_NO_TERMINAL_EVENT" not in codes(trace_advice(absent))

        present = summarise_trace(cut_short())
        assert present["episode"]["event_column"] is True
        assert "TR_NO_TERMINAL_EVENT" in codes(trace_advice(present))

    def test_a_non_finite_column_is_refused_rather_than_filtered(self) -> None:
        """Dropping the bad row would leave a mean over a different set of
        samples than the reader thinks they are looking at."""
        broken = cut_short()
        broken.loc[10, "clearance_m"] = float("nan")
        summary = summarise_trace(broken)
        assert summary["clearance"]["min_m"] is None
        assert summary["progress"]["path_length_m"] is not None

    def test_the_order_is_stable(self, stuck: dict[str, Any]) -> None:
        """Rules fire in whatever order the module evaluates them; a list
        that reshuffles between identical runs is one nobody can diff."""
        first = [a.code for a in trace_advice(stuck)]
        second = [a.code for a in trace_advice(stuck)]
        assert first == second
        assert first == ["TR_STALLED_BEFORE_END", "TR_OSCILLATING", "TR_SPINNING_IN_PLACE"]

    def test_blocking_advice_is_ordered_first(self) -> None:
        severities = [a.severity for a in trace_advice(summarise_trace(collided()))]
        assert severities == sorted(
            severities, key=lambda s: {"blocking": 0, "material": 1, "disclosure": 2}[s]
        )

    def test_summarising_is_deterministic(self, stuck: dict[str, Any]) -> None:
        assert summarise_trace(
            pq.read_table(TRACES / STUCK[0] / f"{STUCK[1]}.parquet").to_pandas(),
            candidate_id=STUCK[0],
            episode_context_id=STUCK[1],
        ) == summarise_trace(
            pq.read_table(TRACES / STUCK[0] / f"{STUCK[1]}.parquet").to_pandas(),
            candidate_id=STUCK[0],
            episode_context_id=STUCK[1],
        )


class TestWhatIsPublished:
    def test_every_emitted_code_is_declared(self) -> None:
        for summary in [*stored_summaries(), *synthetic_summaries().values()]:
            assert codes(trace_advice(summary)) <= set(TRACE_REVIEW_CODES)

    def test_the_codes_are_unique_and_sorted(self) -> None:
        assert len(TRACE_REVIEW_CODES) == len(set(TRACE_REVIEW_CODES))
        assert list(TRACE_REVIEW_CODES) == sorted(TRACE_REVIEW_CODES)

    def test_everything_is_tagged_as_diagnosis(self) -> None:
        for summary in [*stored_summaries(), *synthetic_summaries().values()]:
            assert all(a.kind == "diagnosis" for a in trace_advice(summary))

    def test_advice_is_frozen(self, stuck: dict[str, Any]) -> None:
        found = trace_advice(stuck)[0]
        with pytest.raises(ValidationError):
            found.claim = "something else"
