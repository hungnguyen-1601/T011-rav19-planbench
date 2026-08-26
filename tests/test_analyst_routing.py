"""W3 — the menu a round is shown, and who picks the check.

Two changes, deliberately independent. Filtering is a **presentation**
change: a card whose evidence this run does not hold would be refused at
admission anyway, and the refusal reads to a model as a broken platform,
so it spends the next turn working around a wall that was never there.
Auto-routing is a **semantic** one, and the only thing in this layer
that moves a metric's meaning: ``checker_selection`` stops being "did
the model pick the right check" and becomes "did the code".

The constraints held here are the ones that make either measurable:
``menu_recall`` is read before a filtered arm is trusted, ``unknown``
keeps a menu to look at, routing happens after declare and admission,
and the four ways a check fails to happen stay four numbers.
"""

from __future__ import annotations

import pytest
from test_analyst_candidates import built
from test_analyst_runner import answer, hypothesis, prepared, scripted

from planbench_analyst.features import RoundFeatures
from planbench_analyst.routing import (
    ROUTING_FAILURES,
    effective_menu,
    failure_counts,
    menu_recall,
    route_for,
)
from planbench_analyst.runner import run_round
from planbench_explanation.catalog import TOOL_CATALOG
from planbench_explanation.integration import TYPICAL_AVAILABLE_EVIDENCE
from planbench_explanation.ledger import EvidenceRef, HypothesisProposal


def proposal(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "hypothesis_id": "hyp-1",
        "hypothesis_statement": "the aisle is closed to this footprint",
        "proposition_type": "geometric_infeasibility",
        "proposed_subject": "costmap_inflation",
        "supports": (EvidenceRef(ref="obs:narrow_gap_refusal:cand_a", kind="observation"),),
    }
    fields.update(overrides)
    return HypothesisProposal(**fields)  # type: ignore[arg-type]


def menu(**overrides):  # type: ignore[no-untyped-def]
    fields = {"available_evidence": TYPICAL_AVAILABLE_EVIDENCE}
    fields.update(overrides)
    return effective_menu(TOOL_CATALOG, **fields)


# --------------------------------------------------------------------------
# The effective menu
# --------------------------------------------------------------------------


def test_a_card_this_run_cannot_serve_is_taken_off_the_menu() -> None:
    without_sidecar = menu(available_evidence=TYPICAL_AVAILABLE_EVIDENCE - {"planning_inputs"})
    served = {card.tool_id for card in without_sidecar.cards}
    assert "replay_global_plan" not in served
    assert "rrt_convergence" not in served


def test_filtering_never_removes_a_way_of_finding_out_which_mechanism() -> None:
    """Filtering fact queries by a mechanism the analyst has not chosen
    yet is circular: those are how it chooses."""
    narrowed = menu(mechanisms=["geometric_infeasibility"])
    served = {card.tool_id for card in narrowed.cards}
    assert "get_episode_observations" in served
    assert "get_known_unknowns" in served


def test_a_check_for_another_mechanism_is_hidden_when_one_is_named() -> None:
    narrowed = menu(mechanisms=["geometric_infeasibility"])
    served = {card.tool_id for card in narrowed.cards}
    assert "gap_vs_footprint" in served
    assert "latency_vs_expanded_nodes" not in served


def test_unknown_keeps_the_whole_evidence_capable_menu() -> None:
    """A round that cannot name a mechanism is exactly the one that
    needs to go and look."""
    narrowed = menu(mechanisms=["unknown"])
    served = {card.tool_id for card in narrowed.cards}
    assert "gap_vs_footprint" in served
    assert "latency_vs_expanded_nodes" in served


def test_the_menu_keeps_the_catalog_version_it_was_cut_from() -> None:
    assert menu().catalog_version == TOOL_CATALOG.catalog_version


# --------------------------------------------------------------------------
# menu_recall, read before a filtered arm is trusted
# --------------------------------------------------------------------------


def test_recall_is_one_when_every_acceptable_tool_survived() -> None:
    narrowed = menu(mechanisms=["geometric_infeasibility"])
    assert (
        menu_recall(narrowed, acceptable_tools=["gap_vs_footprint", "get_map_region_features"])
        == 1.0
    )


def test_recall_falls_when_the_filter_removed_what_the_case_needed() -> None:
    """Every downstream number would then be measuring the filter, and
    the failure is invisible afterwards: the round simply never asks."""
    narrowed = menu(mechanisms=["geometric_infeasibility"])
    assert menu_recall(narrowed, acceptable_tools=["latency_vs_expanded_nodes"]) == 0.0


def test_a_case_with_no_acceptable_tools_is_not_a_failure() -> None:
    assert menu_recall(menu(), acceptable_tools=[]) == 1.0


# --------------------------------------------------------------------------
# The code route
# --------------------------------------------------------------------------


def test_the_router_picks_the_checker_for_a_declared_mechanism() -> None:
    route, reason = route_for(
        proposal(),
        catalog=TOOL_CATALOG,
        packet=built(),
        available_evidence=TYPICAL_AVAILABLE_EVIDENCE,
    )
    assert reason == ""
    assert route is not None
    assert route.tool_id == "gap_vs_footprint"
    assert route.chosen_by == "code_route"


def test_the_route_fills_only_arguments_the_card_sources_from_the_packet() -> None:
    """An analyst argument filled with a default would be the platform
    choosing the experiment and then grading the answer."""
    route, _ = route_for(
        proposal(),
        catalog=TOOL_CATALOG,
        packet=built(),
        available_evidence=TYPICAL_AVAILABLE_EVIDENCE,
    )
    assert route is not None
    assert set(route.arguments) == {"candidate_id", "region_id"}
    assert route.arguments["candidate_id"] == "cand_a"


def test_an_analyst_argument_is_left_out_rather_than_defaulted() -> None:
    """``budget_multiplier`` is the analyst's choice of experiment. A
    router that filled it would be the platform choosing how hard to
    look and then grading what it found."""
    sidecar = TYPICAL_AVAILABLE_EVIDENCE | {
        "planning_inputs",
        "seed_set",
        "planner_parameters",
        "planner_implementation_version",
    }
    route, reason = route_for(
        proposal(
            proposition_type="sampling_budget_insufficiency", proposed_subject="global_planner"
        ),
        catalog=TOOL_CATALOG,
        packet=built(),
        available_evidence=frozenset(sidecar),
    )
    assert reason == ""
    assert route is not None
    assert "budget_multiplier" not in route.arguments


def test_a_mechanism_with_no_check_is_declined_by_name() -> None:
    route, reason = route_for(
        proposal(proposition_type="perception_attribution", proposed_subject="perception_provider"),
        catalog=TOOL_CATALOG,
        packet=built(),
        available_evidence=TYPICAL_AVAILABLE_EVIDENCE,
    )
    assert route is None
    assert reason == "tool_not_in_menu"


def test_a_run_that_never_recorded_the_evidence_is_a_different_reason() -> None:
    route, reason = route_for(
        proposal(),
        catalog=TOOL_CATALOG,
        packet=built(),
        available_evidence=frozenset(),
    )
    assert route is None
    assert reason == "missing_required_evidence"


def test_an_argument_the_packet_cannot_supply_is_a_third_reason() -> None:
    """A region id guessed to make the call go through is a checker
    answering about a passage nobody looked at."""
    from test_analyst_packet_view import observation
    from test_analyst_packet_view import packet as bare_packet

    route, reason = route_for(
        proposal(),
        catalog=TOOL_CATALOG,
        packet=bare_packet(observations=[observation()]),
        available_evidence=TYPICAL_AVAILABLE_EVIDENCE,
    )
    assert route is None
    assert reason == "missing_required_argument"


def test_a_question_already_answered_is_the_fourth_reason() -> None:
    route, _ = route_for(
        proposal(),
        catalog=TOOL_CATALOG,
        packet=built(),
        available_evidence=TYPICAL_AVAILABLE_EVIDENCE,
    )
    assert route is not None
    shaped = tuple(sorted((name, str(value)) for name, value in route.arguments.items()))
    again, reason = route_for(
        proposal(),
        catalog=TOOL_CATALOG,
        packet=built(),
        available_evidence=TYPICAL_AVAILABLE_EVIDENCE,
        answered=((route.tool_id, shaped),),
    )
    assert again is None
    assert reason == "repeat_after_verdict"


def test_the_four_failures_are_always_four_numbers() -> None:
    """A table that omitted the zeros would let a reader mistake "this
    never happened" for "nobody measured it"."""
    counts = failure_counts({"tool_not_in_menu": 2})
    assert set(counts) == set(ROUTING_FAILURES)
    assert counts["tool_not_in_menu"] == 2
    assert counts["repeat_after_verdict"] == 0


# --------------------------------------------------------------------------
# The round
# --------------------------------------------------------------------------


def test_both_flags_are_off_unless_the_arm_declares_them() -> None:
    outcome = run_round(prepared(), scripted(answer(hypothesis())))
    assert not any(event.startswith("menu:") for event in outcome.events)
    assert not any(event.startswith("routed:") for event in outcome.events)


def test_a_filtered_round_records_how_much_of_the_menu_it_showed() -> None:
    outcome = run_round(
        prepared(),
        scripted(answer(hypothesis())),
        features=RoundFeatures(candidate_shortlist=True, filter_tool_menu=True),
    )
    (event,) = [item for item in outcome.events if item.startswith("menu:")]
    shown, whole = event.removeprefix("menu:").split("/")
    assert int(shown) <= int(whole)


def test_a_routed_round_says_the_code_chose_the_check() -> None:
    """Without this line in the transcript, ``checker_selection`` would
    silently change meaning the day the flag went on."""
    outcome = run_round(
        prepared(),
        scripted(answer(hypothesis(requested_check=None))),
        features=RoundFeatures(auto_route_checker=True),
    )
    routed = [item for item in outcome.events if item.startswith("routed:")]
    declined = [item for item in outcome.events if item.startswith("route_declined:")]
    assert routed or declined
    if routed:
        assert routed[0].endswith(":code_route")


def test_the_router_leaves_a_hypothesis_that_asked_for_its_own_check_alone() -> None:
    """The model's choice is the thing being measured when this flag is
    off, and overwriting it would measure neither."""
    outcome = run_round(
        prepared(),
        scripted(answer(hypothesis())),
        features=RoundFeatures(auto_route_checker=True),
    )
    assert not any(event.startswith("routed:") for event in outcome.events)


@pytest.mark.parametrize("flag", ["filter_tool_menu", "auto_route_checker"])
def test_each_flag_changes_the_runtime_identity(flag: str) -> None:
    from planbench_analyst.identity import runtime_config_checksum

    def checksum(features: RoundFeatures) -> str:
        return runtime_config_checksum(
            prompt_checksum="a" * 64,
            generation_config={"temperature": 0.0},
            catalog_version=TOOL_CATALOG.catalog_version,
            source_manifest_hash="b" * 64,
            features=features,
        )

    assert checksum(RoundFeatures(**{flag: True})) != checksum(RoundFeatures())  # type: ignore[arg-type]
