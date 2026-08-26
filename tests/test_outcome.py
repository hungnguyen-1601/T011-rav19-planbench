"""Why a run ended the way it did — numbers joined to natures.

Two failure modes matter more than the happy path. The module must not
flatter: a NEAR_EQUIVALENT margin must come back as "no established
difference", never as a win with a hedge. And it must not read a gate
elimination as a ranking loss — a candidate that never qualified was
never compared, and "X beat Y" would be a sentence about a comparison
that did not happen.

The trait table is held to its anchors: every family entry names where
its claims can be checked, and the registry-flag anchors are asserted
against the registry itself so folklore cannot drift in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from planbench_benchmark.outcome import OUTCOME_CODES, TRAITS, build_outcome, outcome_advice
from planbench_benchmark.registry import algorithm_info
from planbench_decision.self_check import exists

STORED = (
    Path(__file__).resolve().parent.parent
    / "artifacts/runs/2026-08-11/open_hall_v2_global_planner_selection_ce26fe87"
    / "comparison_report.json"
)


@pytest.fixture
def stored_report() -> dict[str, Any]:
    if not STORED.exists():
        pytest.skip("stored run not present in this checkout")
    return json.loads(STORED.read_text(encoding="utf-8"))


def codes(source: dict[str, Any]) -> set[str]:
    return {a.code for a in outcome_advice(source)}


def card(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "CLEAR_RECOMMENDATION",
        "recommended": {"candidate_id": "aaa", "stack": "rrtstar+dwa"},
        "evidence": {
            "delta_u_vs_second": 0.04,
            "delta_u_mean": 0.05,
            "ci95": [0.01, 0.09],
            "n_episodes": 30,
            "effect_size": 0.4,
        },
    }
    base.update(overrides)
    return base


def two_candidates(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "identity": {"experiment_scope": "global_planner_selection"},
        "candidates": [
            {
                "candidate_id": "aaa",
                "stack_label": "rrtstar+dwa",
                "blocking_gates": [],
                "success_rate": 1.0,
                "pooled_p99_latency_ms": 40.0,
            },
            {
                "candidate_id": "bbb",
                "stack_label": "astar+dwa",
                "blocking_gates": [],
                "success_rate": 0.97,
                "pooled_p99_latency_ms": 5.0,
            },
        ],
    }
    report.update(overrides)
    return report


class TestOnTheRealStoredRun:
    def test_a_gate_elimination_is_not_called_a_ranking_loss(self, stored_report) -> None:
        found = outcome_advice(build_outcome(stored_report))
        eliminated = next(a for a in found if a.code == "OC_ELIMINATED_BY_GATE")
        assert "eliminated at G3" in eliminated.claim
        assert "winning" in eliminated.do_not

    def test_the_losers_relevant_weakness_is_named(self, stored_report) -> None:
        """The join this module exists for: the number says who, the
        trait says where to look first."""
        found = outcome_advice(build_outcome(stored_report))
        eliminated = next(a for a in found if a.code == "OC_ELIMINATED_BY_GATE")
        assert "dwa" in eliminated.ground

    def test_the_separating_metric_is_named_with_both_numbers(self, stored_report) -> None:
        found = outcome_advice(build_outcome(stored_report))
        driver = next(a for a in found if a.code == "OC_METRIC_DRIVER")
        assert "100%" in driver.claim
        assert "70%" in driver.claim

    def test_the_scope_isolation_is_stated(self, stored_report) -> None:
        found = outcome_advice(build_outcome(stored_report))
        assert any(a.code == "OC_SAME_CONTROLLER_ISOLATES_PLANNER" for a in found)

    def test_every_citation_resolves(self, stored_report) -> None:
        source = build_outcome(stored_report)
        for item in outcome_advice(source):
            assert exists(source, item.field_path), f"{item.code} cites {item.field_path}"


class TestItDoesNotFlatter:
    def test_a_ci_containing_zero_names_no_winner(self) -> None:
        report = two_candidates(
            decision_card=card(
                status="CLEAR_RECOMMENDATION",
                evidence={
                    "delta_u_vs_second": 0.01,
                    "delta_u_mean": 0.01,
                    "ci95": [-0.02, 0.04],
                    "n_episodes": 30,
                    "effect_size": 0.1,
                },
            )
        )
        found = outcome_advice(build_outcome(report))
        assert any(a.code == "OC_MARGIN_IS_NOISE" for a in found)
        assert not any(a.code == "OC_WINNER_ON_MARGIN" for a in found)

    def test_a_near_equivalent_status_is_noise_whatever_the_interval(self) -> None:
        report = two_candidates(decision_card=card(status="NEAR_EQUIVALENT"))
        assert "OC_MARGIN_IS_NOISE" in codes(build_outcome(report))

    def test_a_supported_margin_still_warns_against_generalising(self) -> None:
        report = two_candidates(decision_card=card())
        found = outcome_advice(build_outcome(report))
        winner = next(a for a in found if a.code == "OC_WINNER_ON_MARGIN")
        assert "generalise" in winner.do_not


class TestNumbersMeetNatures:
    def test_a_sampling_planners_latency_tail_is_expected_not_a_bug(self) -> None:
        found = outcome_advice(build_outcome(two_candidates()))
        priced = next(a for a in found if a.code == "OC_LATENCY_PRICE_OF_SAMPLING")
        assert priced.subject == "aaa"
        assert "price of sampling" in priced.ground

    def test_the_same_tail_on_a_deterministic_planner_is_a_surprise(self) -> None:
        report = two_candidates()
        report["candidates"][0]["stack_label"] = "astar+dwa"
        report["candidates"][0]["candidate_id"] = "det"
        found = outcome_advice(build_outcome(report))
        surprise = next(a for a in found if a.code == "OC_TRAIT_SURPRISE")
        assert surprise.severity == "material"
        assert "nothing in its nature predicts" in surprise.claim

    def test_a_wide_success_gap_outranks_latency_talk(self) -> None:
        report = two_candidates()
        report["candidates"][1]["success_rate"] = 0.5
        found = codes(build_outcome(report))
        assert "OC_METRIC_DRIVER" in found


class TestTheTraitTableIsAnchored:
    def test_every_family_names_its_anchor(self) -> None:
        for name, entry in TRAITS.items():
            assert entry.get("anchor"), name

    def test_registry_flag_anchors_agree_with_the_registry(self) -> None:
        """ "rrtstar is stochastic" is the registry's claim, quoted — if
        the registry changes, this table must fail loudly rather than
        keep narrating a property that is gone."""
        assert algorithm_info("rrtstar+dwa").stochastic_global_planner is True
        assert "stochastic_global_planner=True" in TRAITS["rrtstar"]["anchor"]
        assert algorithm_info("astar+dwa").stochastic_global_planner is False
        assert algorithm_info("astar+ppo").requires_model is True
        assert "requires_model=True" in TRAITS["ppo"]["anchor"]

    def test_every_stack_component_in_the_registry_has_traits(self) -> None:
        from planbench_benchmark.registry import list_algorithms

        for info in list_algorithms():
            assert info.global_planner in TRAITS, info.global_planner
            assert info.local_controller in TRAITS, info.local_controller


class TestItNeverBreaks:
    def test_an_empty_source_returns_nothing(self) -> None:
        assert outcome_advice({}) == ()

    def test_a_malformed_report_returns_nothing(self) -> None:
        assert outcome_advice({"report": {"candidates": "not a list"}}) == ()

    def test_an_unknown_stack_label_still_works(self) -> None:
        report = two_candidates()
        report["candidates"][0]["stack_label"] = "teb+mppi"
        assert isinstance(outcome_advice(build_outcome(report)), tuple)

    def test_the_order_is_stable(self, stored_report) -> None:
        source = build_outcome(stored_report)
        assert [a.code for a in outcome_advice(source)] == [a.code for a in outcome_advice(source)]


class TestWhatIsPublished:
    def test_every_emitted_code_is_declared(self, stored_report) -> None:
        emitted = codes(build_outcome(stored_report))
        emitted |= codes(build_outcome(two_candidates(decision_card=card())))
        emitted |= codes(
            build_outcome(two_candidates(decision_card=card(status="NEAR_EQUIVALENT")))
        )
        assert emitted <= set(OUTCOME_CODES), emitted - set(OUTCOME_CODES)

    def test_everything_is_tagged_as_diagnosis(self, stored_report) -> None:
        assert all(a.kind == "diagnosis" for a in outcome_advice(build_outcome(stored_report)))
