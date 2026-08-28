"""Assembling one episode from what the platform serves, and refusing well.

The builder does no arithmetic of its own, so most of what is worth
testing is what it does when a piece is missing: one trace unreadable,
no sidecar, a report that never scored the episode. Every one of those
has a wrong behaviour that looks reasonable — carry on silently, or
raise and produce nothing — and the right one is to build what can be
built and write the gap down.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from planbench_explanation.case_packet import RobotFacts
from planbench_explanation.episode_builder import (
    SELECTED_ROLE,
    SIDECAR_SUFFIX,
    EpisodeBuildRefusal,
    build_episode_packet,
    components_from_report,
    detections_for,
    episode_rows,
    planning_summary,
)
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.ledger import KnownUnknown
from planbench_explanation.packet_builder import DeploymentThresholds
from planbench_explanation.versioning import ExplanationArtifactHeader

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "visible"
EPISODE = "ep-004"
EPSILON = 0.005


def header() -> ExplanationArtifactHeader:
    return ExplanationArtifactHeader.for_current_code(
        source_manifest_ref="runs/2026-08-27/abc/manifest.json",
        source_manifest_checksum="a" * 64,
        detector_version="0.1.0",
        knowledge_base_version=KNOWLEDGE_BASE_VERSION,
        tool_catalog_version="3.4.0",
    )


def report(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "candidates": [
            {
                "candidate_id": "A",
                "stack_label": "astar+dwa",
                "components": {
                    "global_planner": "astar",
                    "local_controller": "dwa",
                    "local_controller_config": "default",
                },
                "episodes": [
                    {
                        "episode_context_id": EPISODE,
                        "success": True,
                        "collision_count": 0,
                        "min_clearance": 0.44,
                        "travel_time_s": 21.0,
                        "p99_latency_ms": 6.1,
                        "replan_count": 1,
                        "episode_decision_utility": 0.88,
                    }
                ],
            },
            {
                "candidate_id": "B",
                "stack_label": "rrtstar+dwa",
                "components": {
                    "global_planner": "rrtstar",
                    "local_controller": "dwa",
                    "local_controller_config": "default",
                },
                "episodes": [
                    {
                        "episode_context_id": EPISODE,
                        "success": True,
                        "collision_count": 0,
                        "min_clearance": 0.19,
                        "travel_time_s": 33.0,
                        "p99_latency_ms": 19.4,
                        "replan_count": 4,
                        "episode_decision_utility": 0.71,
                    }
                ],
            },
        ]
    }
    base.update(overrides)
    return base


def trace(
    *,
    candidate_id: str = "A",
    episode_context_id: str = EPISODE,
    stalls: bool = False,
    columns: bool = True,
) -> dict[str, Any]:
    """A short straight run, optionally with a stall in the middle."""
    steps = 40
    times = [round(index * 0.1, 3) for index in range(steps)]
    xs: list[float] = []
    position = 0.0
    for index in range(steps):
        if stalls and 12 <= index < 30:
            pass  # standing still: the stuck detector reads speed, not time
        else:
            position += 0.25
        xs.append(round(position, 4))
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "episode_context_id": episode_context_id,
        "t": times,
        "x": xs,
        "y": [0.0] * steps,
        "events": [],
    }
    if columns:
        payload["clearance_m"] = [0.5] * steps
        payload["planner_latency_ms"] = [5.0] * steps
    return payload


def build(**overrides: Any):
    fields: dict[str, Any] = {
        "header": header(),
        "run_id": "run-1",
        "episode_context_id": EPISODE,
        "candidate_a": "A",
        "candidate_b": "B",
        "report": report(),
        "trace_a": trace(candidate_id="A"),
        "trace_b": trace(candidate_id="B", stalls=True),
        "tie_epsilon": EPSILON,
    }
    fields.update(overrides)
    return build_episode_packet(**fields)


class TestReadingTheReport:
    def test_rows_are_keyed_by_episode(self) -> None:
        rows = episode_rows(report(), "A")
        assert set(rows) == {EPISODE}

    def test_a_candidate_the_report_never_mentions_has_no_rows(self) -> None:
        assert episode_rows(report(), "Z") == {}

    def test_components_come_from_the_report_rather_than_a_label_split(self) -> None:
        """Splitting ``astar+dwa`` on a plus works until a stack has a
        hyphenated name or three parts, and then it compares the wrong things."""
        parts = components_from_report(report(), "B")
        assert parts is not None
        assert (parts.global_planner, parts.local_controller) == ("rrtstar", "dwa")

    def test_a_report_with_no_stack_for_a_candidate_refuses_the_build(self) -> None:
        thin = report(candidates=[{"candidate_id": "A", "episodes": []}])
        with pytest.raises(EpisodeBuildRefusal):
            build(report=thin)


class TestTheBuild:
    def test_the_verdict_comes_out_of_the_scored_rows(self) -> None:
        packet = build()
        assert packet.verdict.basis == "episode_decision_utility"
        assert packet.verdict.winner == "A"

    def test_both_candidates_get_a_diagnosis_even_with_one_trace_missing(self) -> None:
        """One unreadable trace is a reason to say so beside the other one's
        findings, not a reason to have no packet."""
        packet = build(trace_b=None)
        assert [item.candidate_id for item in packet.diagnoses] == ["A", "B"]
        assert any("no trace was served for B" in note for note in packet.omissions)

    def test_a_missing_row_makes_the_episode_not_comparable(self) -> None:
        only_a = report()
        only_a["candidates"][1]["episodes"] = []
        packet = build(report=only_a)
        assert packet.verdict.basis == "not_comparable"
        assert packet.verdict.winner is None
        assert packet.contrasts == (), "nothing may be stated against a side nobody named"

    def test_the_episode_is_the_one_asked_for(self) -> None:
        packet = build()
        assert packet.episode_context_id == EPISODE
        assert packet.verdict.episode_context_id == EPISODE

    def test_a_run_statistical_gap_arrives_as_context_and_blocks_nothing(self) -> None:
        gap = KnownUnknown(
            id="prevalence_unavailable",
            blocks_claim_types=("local_minimum_entrapment",),
            source="too few episodes to call it a pattern",
        )
        packet = build(run_context_unknowns=(gap,))
        assert gap in packet.run_context_unknowns
        assert "local_minimum_entrapment" not in packet.blocked_claim_types

    def test_a_platform_gap_arrives_carrying_its_force(self) -> None:
        from planbench_explanation.case_packet import STANDING_UNKNOWNS

        packet = build(run_context_unknowns=STANDING_UNKNOWNS)
        assert packet.run_context_unknowns == ()
        assert "candidate_latency_attribution" in packet.blocked_claim_types

    def test_a_trace_without_clearance_blocks_the_claim_that_reads_it(self) -> None:
        """The detector never ran, so it never found anything."""
        packet = build(
            trace_a=trace(candidate_id="A", columns=False),
            trace_b=trace(candidate_id="B", columns=False),
        )
        assert "clearance_refusal" in packet.blocked_claim_types

    def test_timelines_are_built_only_when_the_thresholds_are_declared(self) -> None:
        assert build().timelines == ()
        with_thresholds = build(
            thresholds=DeploymentThresholds(
                robot_radius_m=0.25,
                control_period_s=0.1,
                clearance_warning_m=0.3,
                max_linear_velocity=1.0,
            )
        )
        for timeline in with_thresholds.timelines:
            assert timeline.role == SELECTED_ROLE
            assert timeline.episode_context_id == EPISODE

    def test_the_role_is_not_borrowed_from_the_exemplar_vocabulary(self) -> None:
        """Calling an episode nobody ranked ``typical`` would be a claim about
        the run's distribution made by a mouse click."""
        from planbench_explanation.packet_builder import TIMELINE_ROLES

        assert SELECTED_ROLE not in TIMELINE_ROLES

    def test_one_candidate_twice_is_refused(self) -> None:
        with pytest.raises(EpisodeBuildRefusal):
            build(candidate_b="A")

    def test_a_trace_from_another_episode_is_refused(self) -> None:
        """Two canvases side by side already assert a paired comparison, and
        one built from two different episodes is the most convincing wrong
        picture this layer could draw."""
        with pytest.raises(EpisodeBuildRefusal):
            build(trace_b=trace(candidate_id="B", episode_context_id="ep-999"))

    def test_a_trace_recording_the_other_candidate_is_refused(self) -> None:
        with pytest.raises(EpisodeBuildRefusal):
            build(trace_b=trace(candidate_id="A"))


class TestPlanningAttempts:
    def test_no_directory_is_not_an_error(self) -> None:
        assert planning_summary(None, candidate_id="A") == {}

    def test_a_directory_without_a_sidecar_is_not_an_error(self, tmp_path: Path) -> None:
        assert planning_summary(tmp_path, candidate_id="A") == {}

    def test_a_real_sidecar_is_summarised(self) -> None:
        case = FIXTURES / "rrt-001"
        if not case.exists():
            pytest.skip("golden fixtures are not present in this checkout")
        directories = sorted(path for path in (case / "sidecar").iterdir() if path.is_dir())
        assert directories, "the rrt-001 fixture is expected to carry a sidecar"
        candidate = directories[0].name
        recorded = sorted(directories[0].glob(f"*{SIDECAR_SUFFIX}"))
        assert recorded, "the sidecar directory is expected to hold a recording"
        episode = recorded[0].name.removesuffix(SIDECAR_SUFFIX)
        summary = planning_summary(
            directories[0], candidate_id=candidate, episode_context_id=episode
        )
        assert summary.get("attempts", 0) >= 1

    def test_an_episode_reads_its_own_file_and_not_a_neighbour(self) -> None:
        """One directory holds every episode a candidate ran. Globbing for
        the first file would summarise another episode's refusals with
        nothing looking wrong."""
        case = FIXTURES / "rrt-001"
        if not case.exists():
            pytest.skip("golden fixtures are not present in this checkout")
        directories = sorted(path for path in (case / "sidecar").iterdir() if path.is_dir())
        summary = planning_summary(
            directories[0], candidate_id=directories[0].name, episode_context_id="ep-not-here"
        )
        assert summary == {} or summary.get("attempts") == 0


class TestAgainstAFixtureThatExists:
    """One pass over a real recorded episode.

    Fixture reports carry no ``success`` and no per-episode utility — the
    planted worlds were never ranked — so this is also the case that
    proves the builder says ``undecidable`` rather than inventing a
    winner out of the columns it does have.
    """

    def test_a_recorded_episode_assembles_and_declines_to_rank(self) -> None:
        case = FIXTURES / "latency-001"
        if not (case / "report.json").exists():
            pytest.skip("golden fixtures are not present in this checkout")
        recorded = json.loads((case / "report.json").read_text(encoding="utf-8"))
        candidates = [entry["candidate_id"] for entry in recorded["candidates"]]
        episode = recorded["candidates"][0]["episodes"][0]["episode_context_id"]

        packet = build_episode_packet(
            header=header(),
            run_id="latency-001",
            episode_context_id=episode,
            candidate_a=candidates[0],
            candidate_b=candidates[1],
            report=recorded,
            trace_a=None,
            trace_b=None,
            tie_epsilon=EPSILON,
            robot=RobotFacts(radius_m=0.25, inflation_margin_m=0.08),
        )
        assert packet.verdict.basis == "undecidable"
        assert packet.verdict.winner is None
        assert packet.contrasts == ()
        assert len(packet.candidates) == 2


class TestDetectorsOverAServedTrace:
    def test_an_empty_trace_is_reported_rather_than_raised(self) -> None:
        found, notes = detections_for({"t": [], "x": [], "y": []})
        assert found == ()
        assert notes and "detectors did not run" in notes[0]

    def test_a_degraded_reference_is_written_down(self) -> None:
        """Arc length measured along the robot's own path is not arc length
        along the route, and a window that does not say so reads as though
        it were."""
        _, notes = detections_for(trace())
        assert any("arc length" in note for note in notes)
