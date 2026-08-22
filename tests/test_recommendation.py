"""The recommendation layer: stored runs in, checkable advice out.

The claims worth testing are the constitutional ones. The per-run verdict
is never re-litigated: whatever the card says is what the advice repeats.
"In which cases" is answered per mission with the same paired bootstrap
that decides the card, and a group too small to bootstrap is described,
never concluded from. Feasibility on this profile trumps history. And an
empty database yields the honest tier-3 answer, not a guess.
"""

from __future__ import annotations

from typing import Any

from task_profile_fakes import make_profile, three_missions

from planbench_benchmark.recommendation import (
    MIN_PAIRS_PER_CASE,
    RECOMMENDATION_CODES,
    case_table,
    map_contexts,
    recommend_from_history,
    recommendation_source,
)
from planbench_benchmark.registry import algorithm_info
from planbench_decision.self_check import exists
from planbench_schemas.episode_context import NOMINAL_VARIANT, EpisodeContext

A_ID = "aaa111aaa111"
B_ID = "bbb222bbb222"


def _context_id(profile, mission_id: str, seed: int) -> str:
    return EpisodeContext(
        task_profile_id=profile.id,
        mission_id=mission_id,
        seed=seed,
        environment_variant=NOMINAL_VARIANT,
        sample_set="evaluation",
    ).episode_context_id


def _report(
    profile,
    *,
    deltas_by_mission: dict[str, list[float]],
    base: float = 0.5,
    extra_context_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """A stored report with exactly the paired utilities the test declares.

    ``deltas_by_mission[m][k]`` is ``U(a) − U(b)`` for seed ``k`` of
    mission ``m`` — the test states the differences and the report is
    built to carry them, so every assertion reads back a number the test
    chose rather than one an engine produced.
    """
    a_episodes, b_episodes = [], []
    for mission_id, deltas in deltas_by_mission.items():
        for seed, delta in enumerate(deltas):
            context = _context_id(profile, mission_id, seed)
            a_episodes.append(
                {"episode_context_id": context, "episode_decision_utility": base + delta}
            )
            b_episodes.append({"episode_context_id": context, "episode_decision_utility": base})
    for foreign in extra_context_ids:
        a_episodes.append({"episode_context_id": foreign, "episode_decision_utility": base})
        b_episodes.append({"episode_context_id": foreign, "episode_decision_utility": base})
    return {
        "comparison_pair": {
            "recommended_candidate_id": A_ID,
            "runner_up_candidate_id": B_ID,
        },
        "candidates": [
            {"candidate_id": A_ID, "stack_label": "rrtstar+dwa", "episodes": a_episodes},
            {"candidate_id": B_ID, "stack_label": "astar+dwa", "episodes": b_episodes},
        ],
    }


def _run_row(profile, report: dict[str, Any], *, run_id: str = "run001", **overrides) -> dict:
    row = {
        "run_id": run_id,
        "status": "CLEAR_RECOMMENDATION",
        "card": {"recommended": {"stack": "rrtstar+dwa", "candidate_id": A_ID}},
        "report": report,
        "created_at": "2026-08-21T00:00:00Z",
        "contracts_version": "6.6.0",
    }
    row.update(overrides)
    return row


class TestContextMapping:
    def test_every_evaluation_context_maps_back_to_its_mission(self):
        profile = make_profile(missions=three_missions())
        wanted = {
            _context_id(profile, mission["id"], seed)
            for mission in three_missions()
            for seed in range(4)
        }
        mapping = map_contexts(profile, wanted)
        assert set(mapping) == wanted
        for mission in three_missions():
            attributed = [m for m in mapping.values() if m["mission_id"] == mission["id"]]
            assert len(attributed) == 4

    def test_a_foreign_id_is_absent_not_guessed(self):
        profile = make_profile()
        mapping = map_contexts(profile, {"deadbeefdead"})
        assert mapping == {}


class TestCaseTable:
    def test_each_mission_gets_its_own_verdict(self):
        """m1 clearly favours A, m2 clearly favours B, m3 cannot tell —
        three verdicts from one run, which is the whole feature."""
        profile = make_profile(missions=three_missions())
        report = _report(
            profile,
            deltas_by_mission={
                "m1": [0.05] * 6,
                "m2": [-0.05] * 6,
                "m3": [0.05, -0.05] * 3,
            },
        )
        table = case_table(profile, report)
        assert table["available"] is True
        verdicts = {case["mission_id"]: case for case in table["cases"]}
        assert verdicts["m1"]["status"] == "CLEAR"
        assert verdicts["m1"]["winner_stack"] == "rrtstar+dwa"
        assert verdicts["m2"]["status"] == "CLEAR"
        assert verdicts["m2"]["winner_stack"] == "astar+dwa"
        assert verdicts["m3"]["status"] == "NEAR_EQUIVALENT"
        assert verdicts["m3"]["winner_stack"] is None

    def test_a_small_group_is_described_never_concluded_from(self):
        profile = make_profile(missions=three_missions())
        report = _report(
            profile,
            deltas_by_mission={"m1": [0.05] * (MIN_PAIRS_PER_CASE - 1)},
        )
        table = case_table(profile, report)
        (case,) = table["cases"]
        assert case["status"] == "INSUFFICIENT_EPISODES"
        assert case["ci95"] is None
        assert case["winner_stack"] is None
        # The description is still there — n and mean — because "too few
        # to conclude" is not "nothing happened".
        assert case["n_pairs"] == MIN_PAIRS_PER_CASE - 1

    def test_unattributable_episodes_are_counted_not_assigned(self):
        profile = make_profile()
        report = _report(
            profile,
            deltas_by_mission={"m1": [0.05] * 6},
            extra_context_ids=("deadbeefdead",),
        )
        table = case_table(profile, report)
        assert table["n_unmapped"] == 1
        assert table["unmapped_contexts"] == ["deadbeefdead"]
        (case,) = table["cases"]
        assert case["n_pairs"] == 6  # the foreign episode joined no mission

    def test_a_run_that_compared_nobody_is_a_stated_absence(self):
        profile = make_profile()
        table = case_table(profile, {"candidates": []})
        assert table["available"] is False
        assert table["cases"] == []

    def test_a_report_without_per_episode_utilities_says_so(self):
        profile = make_profile()
        report = _report(profile, deltas_by_mission={"m1": [0.05] * 6})
        for candidate in report["candidates"]:
            candidate["episodes"] = []
        table = case_table(profile, report)
        assert table["available"] is False
        assert "predates" in table["reason"]


class TestFeasibilityTrumpsHistory:
    def test_ppo_is_blocked_without_a_chosen_model(self):
        source = recommendation_source(make_profile(), [])
        advice = recommend_from_history(source)
        blocked = [a for a in advice if a.code == "RC_FEASIBILITY_EXCLUDES"]
        assert any(a.subject == "astar+ppo" for a in blocked)
        assert any("PF_MODEL_NOT_CHOSEN" in a.claim for a in blocked)

    def test_a_withdrawn_stack_carries_the_registry_verbatim(self):
        source = recommendation_source(make_profile(), [])
        advice = recommend_from_history(source)
        withdrawn = {a.subject: a for a in advice if a.code == "RC_NOT_PRODUCTION_ELIGIBLE"}
        assert "astar+dwa_predictive" in withdrawn
        registry_reason = algorithm_info("astar+dwa_predictive").withdrawn
        assert registry_reason  # the registry does record why
        assert withdrawn["astar+dwa_predictive"].ground == registry_reason

    def test_reference_adapters_are_disclosed_too(self):
        source = recommendation_source(make_profile(), [])
        advice = recommend_from_history(source)
        subjects = {a.subject for a in advice if a.code == "RC_NOT_PRODUCTION_ELIGIBLE"}
        assert "astar+pure_pursuit" in subjects
        assert "rrtstar+pure_pursuit" in subjects


class TestHistoryRules:
    def test_no_runs_is_the_honest_tier_three_answer(self):
        source = recommendation_source(make_profile(), [])
        assert source["evidence_tier"] == 3
        advice = recommend_from_history(source)
        (empty,) = [a for a in advice if a.code == "RC_NO_COMPARABLE_HISTORY"]
        # The remedy names what is actually runnable today.
        assert "astar+dwa" in empty.do
        assert "rrtstar+dwa" in empty.do
        assert "astar+ppo" not in empty.do  # blocked, so not offered

    def test_a_card_on_this_profile_is_repeated_never_recomputed(self):
        profile = make_profile()
        report = _report(profile, deltas_by_mission={"m1": [0.05] * 6})
        source = recommendation_source(profile, [_run_row(profile, report)])
        assert source["evidence_tier"] == 1
        advice = recommend_from_history(source)
        (card,) = [a for a in advice if a.code == "RC_CARD_ON_THIS_PROFILE"]
        assert "rrtstar+dwa" in card.claim
        assert card.subject == "run001"

    def test_near_equivalent_forbids_reading_better(self):
        profile = make_profile()
        report = _report(profile, deltas_by_mission={"m1": [0.05, -0.05] * 3})
        row = _run_row(profile, report, status="NEAR_EQUIVALENT")
        advice = recommend_from_history(recommendation_source(profile, [row]))
        (honesty,) = [a for a in advice if a.code == "RC_NEAR_EQUIVALENT_HONESTY"]
        assert "better" in honesty.do_not
        assert not [a for a in advice if a.code == "RC_CARD_ON_THIS_PROFILE"]

    def test_two_agreeing_runs_are_consensus(self):
        profile = make_profile()
        report = _report(profile, deltas_by_mission={"m1": [0.05] * 6})
        rows = [
            _run_row(profile, report, run_id="run001"),
            _run_row(profile, report, run_id="run002"),
        ]
        advice = recommend_from_history(recommendation_source(profile, rows))
        assert [a for a in advice if a.code == "RC_CONSENSUS_ACROSS_RUNS"]
        assert not [a for a in advice if a.code == "RC_CONFLICT_BETWEEN_RUNS"]

    def test_two_disagreeing_runs_are_a_named_conflict_not_a_vote(self):
        profile = make_profile()
        report = _report(profile, deltas_by_mission={"m1": [0.05] * 6})
        rows = [
            _run_row(profile, report, run_id="run001"),
            _run_row(
                profile,
                report,
                run_id="run002",
                card={"recommended": {"stack": "astar+dwa", "candidate_id": B_ID}},
            ),
        ]
        advice = recommend_from_history(recommendation_source(profile, rows))
        (conflict,) = [a for a in advice if a.code == "RC_CONFLICT_BETWEEN_RUNS"]
        assert "astar+dwa" in conflict.claim and "rrtstar+dwa" in conflict.claim
        assert "vote" in conflict.do_not

    def test_single_mission_discloses_that_cases_cannot_differ(self):
        profile = make_profile()  # one mission
        report = _report(profile, deltas_by_mission={"m1": [0.05] * 6})
        advice = recommend_from_history(recommendation_source(profile, [_run_row(profile, report)]))
        assert [a for a in advice if a.code == "RC_SINGLE_CASE_ONLY"]

    def test_per_case_winners_surface_as_advice(self):
        profile = make_profile(missions=three_missions())
        report = _report(
            profile,
            deltas_by_mission={"m1": [0.05] * 6, "m2": [-0.05] * 6, "m3": [0.05, -0.05] * 3},
        )
        advice = recommend_from_history(recommendation_source(profile, [_run_row(profile, report)]))
        winners = {a.subject: a for a in advice if a.code == "RC_CASE_WINNER"}
        assert set(winners) == {"m1", "m2"}
        assert "rrtstar+dwa beat astar+dwa" in winners["m1"].claim
        assert "astar+dwa beat rrtstar+dwa" in winners["m2"].claim
        undecided = [a for a in advice if a.code == "RC_CASE_UNDECIDED"]
        assert [a.subject for a in undecided] == ["m3"]
        # Multi-mission profile: the single-case disclosure must NOT fire.
        assert not [a for a in advice if a.code == "RC_SINGLE_CASE_ONLY"]


class TestTheConstitution:
    def test_every_citation_resolves_against_the_source(self):
        profile = make_profile(missions=three_missions())
        report = _report(
            profile,
            deltas_by_mission={"m1": [0.05] * 6, "m2": [0.05, -0.05] * 3},
            extra_context_ids=("deadbeefdead",),
        )
        source = recommendation_source(profile, [_run_row(profile, report)])
        advice = recommend_from_history(source)
        assert advice  # a silent pass would prove nothing
        for item in advice:
            assert exists(source, item.field_path), item.code

    def test_same_input_same_advice(self):
        profile = make_profile(missions=three_missions())
        report = _report(profile, deltas_by_mission={"m1": [0.05] * 6})
        rows = [_run_row(profile, report)]
        first = recommend_from_history(recommendation_source(profile, rows))
        second = recommend_from_history(recommendation_source(profile, rows))
        assert first == second

    def test_garbage_in_advice_never_raises(self):
        assert recommend_from_history({"runs": object()}) == ()

    def test_every_code_fired_here_is_published(self):
        profile = make_profile(missions=three_missions())
        report = _report(
            profile,
            deltas_by_mission={
                "m1": [0.05] * 6,
                "m2": [0.05, -0.05] * 3,
                "m3": [0.05] * (MIN_PAIRS_PER_CASE - 1),
            },
            extra_context_ids=("deadbeefdead",),
        )
        advice = recommend_from_history(recommendation_source(profile, [_run_row(profile, report)]))
        assert {a.code for a in advice} <= set(RECOMMENDATION_CODES)

    def test_no_advice_carries_an_action_verb_toward_the_platform(self):
        """Advice is text. Nothing here launches, approves or writes —
        the strings say what a person should do, and the person is the
        one with the verbs."""
        profile = make_profile()
        advice = recommend_from_history(recommendation_source(profile, []))
        for item in advice:
            assert "declare_safe" not in item.do
            assert item.kind == "recommendation"
