"""Explaining a gate, without becoming a second gate.

Two things must hold. The advice must never disagree with the verdict it
explains — a module that could re-decide a gate would be a gate with no
contract behind it. And every failed gate must name the move that is
barred, because each one has a remedy that makes the symptom vanish
without making the conclusion true, and it is one form field away.

The fixture is a real stored run: `open_hall_v2`, where `astar+dwa`
failed G3 at 70% against 85% required and `rrtstar+dwa` cleared
everything. Nothing here is hand-written except the task profile's
thresholds, which the report genuinely does not carry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from planbench_decision.gate_advice import GATE_ADVICE_CODES, build_diagnosis, gate_advice
from planbench_decision.self_check import exists

STORED = (
    Path(__file__).resolve().parent.parent
    / "artifacts/runs/2026-08-11/open_hall_v2_global_planner_selection_ce26fe87"
    / "comparison_report.json"
)

PROFILE: dict[str, Any] = {
    "constraints": {
        "success_rate_min": 0.85,
        "no_path_rate_max": 0.02,
        "collision_probability_max": 0.1,
    }
}


@pytest.fixture
def report() -> dict[str, Any]:
    if not STORED.exists():
        pytest.skip("stored run not present in this checkout")
    return json.loads(STORED.read_text())


@pytest.fixture
def advice(report: dict[str, Any]) -> tuple[Any, ...]:
    return gate_advice(build_diagnosis(report, PROFILE))


def codes(items: tuple[Any, ...]) -> set[str]:
    return {a.code for a in items}


class TestItExplainsTheGateThatFailed:
    def test_the_failed_gate_is_named(self, advice: tuple[Any, ...]) -> None:
        assert "GA_G3_SUCCESS_RATE" in codes(advice)

    def test_it_carries_both_numbers_the_report_alone_cannot(self, advice: tuple[Any, ...]) -> None:
        """`G3: "fail"` is a bare string. The rate observed lives on the
        candidate and the rate required lives on the task profile, so
        advice naming only one is advice a reader cannot check."""
        found = next(a for a in advice if a.code == "GA_G3_SUCCESS_RATE")
        assert "70%" in found.claim
        assert "85%" in found.claim

    def test_it_says_which_candidate(self, advice: tuple[Any, ...]) -> None:
        found = next(a for a in advice if a.code == "GA_G3_SUCCESS_RATE")
        assert found.subject == "60c8e26fe591"

    def test_a_gate_that_passed_draws_no_failure_advice(self, advice: tuple[Any, ...]) -> None:
        """`rrtstar+dwa` cleared everything; advice against it would be
        the module inventing a problem."""
        for item in advice:
            if item.subject == "db26440f6052":
                assert item.severity != "blocking", item.code

    def test_a_run_with_no_card_says_so_once(self, advice: tuple[Any, ...]) -> None:
        found = [a for a in advice if a.code == "GA_NOBODY_CLEARED"]
        assert len(found) == 1
        assert "1 of 2" in found[0].claim


class TestItReadsBothGateShapes:
    """G1, G3 and G6 report a bare string; G2, G4 and G5 report a dict.
    A reader of one shape silently skips half the gates."""

    def test_a_bare_string_verdict_is_understood(self) -> None:
        report = {
            "candidates": [{"candidate_id": "x", "gates": {"G3": "fail"}, "success_rate": 0.4}]
        }
        assert "GA_G3_SUCCESS_RATE" in codes(gate_advice(build_diagnosis(report, PROFILE)))

    def test_a_dict_verdict_is_understood(self) -> None:
        report = {
            "candidates": [
                {
                    "candidate_id": "x",
                    "gates": {"G2": {"result": "fail", "observed": 2, "n_min": 30, "n_runs": 30}},
                }
            ]
        }
        assert "GA_G2_COLLISION" in codes(gate_advice(build_diagnosis(report, PROFILE)))

    def test_a_collision_and_a_short_sample_are_two_different_problems(self) -> None:
        """Both fail G2, and the remedies are opposites: one is a safety
        defect, the other is not enough evidence."""
        report = {
            "candidates": [
                {
                    "candidate_id": "x",
                    "gates": {
                        "G2": {
                            "result": "fail",
                            "observed": 1,
                            "n_min": 30,
                            "n_distinct_episodes": 12,
                        }
                    },
                }
            ]
        }
        found = codes(gate_advice(build_diagnosis(report, PROFILE)))
        assert {"GA_G2_COLLISION", "GA_G2_TOO_FEW_EPISODES"} <= found


class TestItNamesTheBarredMove:
    def test_every_blocking_advice_names_one(self, advice: tuple[Any, ...]) -> None:
        for item in advice:
            if item.severity == "blocking":
                assert item.do_not, item.code

    def test_the_threshold_edit_is_named_explicitly(self, advice: tuple[Any, ...]) -> None:
        """Lowering `success_rate_min` is one field away in a form the
        same person may edit. Leaving it implicit is how it gets done."""
        found = next(a for a in advice if a.code == "GA_G3_SUCCESS_RATE")
        assert "success_rate_min" in found.do_not

    def test_the_risk_edit_is_named_where_it_would_shrink_n_min(self) -> None:
        report = {
            "candidates": [
                {
                    "candidate_id": "x",
                    "gates": {"G2": {"result": "fail", "observed": 0, "n_min": 3000, "n_runs": 30}},
                }
            ]
        }
        found = next(
            a
            for a in gate_advice(build_diagnosis(report, PROFILE))
            if a.code == "GA_G2_TOO_FEW_EPISODES"
        )
        assert "collision_probability_max" in found.do_not

    def test_the_observation_edit_is_named(self) -> None:
        report = {
            "candidates": [
                {"candidate_id": "x", "gates": {"G6": {"result": "fail", "missing": ["depth"]}}}
            ]
        }
        found = next(
            a
            for a in gate_advice(build_diagnosis(report, PROFILE))
            if a.code == "GA_G6_OBSERVATION"
        )
        assert "available_observations" in found.do_not


class TestItDisclosesWhatPassedButShouldBeSaid:
    def test_a_host_only_latency_screening_is_disclosed(self, advice: tuple[Any, ...]) -> None:
        """G4 passed. It passed on a laptop, and the report says so in a
        caveat nobody reads."""
        found = [a for a in advice if a.code == "GA_G4_HOST_ONLY"]
        assert found
        assert all(a.severity == "disclosure" for a in found)

    def test_an_unpinned_measurement_is_flagged(self) -> None:
        report = {
            "candidates": [],
            "measurement_environment": {"warning": "cpu affinity could not be set"},
        }
        assert "GA_UNPINNED_MEASUREMENT" in codes(gate_advice(build_diagnosis(report, PROFILE)))


class TestEveryCitationResolves:
    def test_against_the_real_stored_run(
        self, report: dict[str, Any], advice: tuple[Any, ...]
    ) -> None:
        source = build_diagnosis(report, PROFILE)
        for item in advice:
            assert exists(source, item.field_path), f"{item.code} cites {item.field_path}"

    def test_with_no_task_profile_supplied(self, report: dict[str, Any]) -> None:
        """A caller that has the report and not the profile still gets
        advice; it just cannot name the threshold."""
        source = build_diagnosis(report)
        for item in gate_advice(source):
            assert exists(source, item.field_path), item.code


class TestItNeverBreaks:
    def test_an_empty_diagnosis_returns_nothing(self) -> None:
        assert gate_advice({}) == ()

    def test_a_malformed_report_returns_nothing_rather_than_raising(self) -> None:
        assert gate_advice({"report": {"candidates": "not a list"}}) == ()

    def test_a_gate_of_an_unexpected_type_is_ignored(self) -> None:
        report = {"candidates": [{"candidate_id": "x", "gates": {"G3": 42}}]}
        assert gate_advice(build_diagnosis(report, PROFILE)) == ()

    def test_the_order_is_stable(self, report: dict[str, Any]) -> None:
        first = [a.code for a in gate_advice(build_diagnosis(report, PROFILE))]
        second = [a.code for a in gate_advice(build_diagnosis(report, PROFILE))]
        assert first == second


class TestWhatIsPublished:
    def test_every_emitted_code_is_declared(self, advice: tuple[Any, ...]) -> None:
        assert codes(advice) <= set(GATE_ADVICE_CODES)

    def test_the_codes_are_unique(self) -> None:
        assert len(GATE_ADVICE_CODES) == len(set(GATE_ADVICE_CODES))

    def test_everything_is_tagged_as_diagnosis(self, advice: tuple[Any, ...]) -> None:
        assert all(a.kind == "diagnosis" for a in advice)
