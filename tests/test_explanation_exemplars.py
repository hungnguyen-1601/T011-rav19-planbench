"""E2 — the four episodes the panel opens with, chosen before the data.

The recipe is the whole point: any hand-picked pair of episodes is a
true statement about two episodes and a misleading picture of thirty.
These tests pin the roles, the tie-break, and the one case the utility
ranking gets wrong on its own — a collision that cost almost no ΔU.
"""

from __future__ import annotations

import pytest
from task_profile_fakes import make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import DecisionSettings
from planbench_decision.pairing import PairingViolation
from planbench_decision.stats import CandidateEvidence, build_evidence
from planbench_explanation.exemplars import (
    EXEMPLAR_ROLES,
    ExemplarRefusal,
    ExemplarSet,
    ReportExemplarRefusal,
    index_metrics,
    select_exemplars,
    select_exemplars_from_report,
)
from planbench_metrics.definitions import EpisodeMetricSet
from planbench_schemas.episode_context import EpisodeContext

STRUCTURAL: dict[str, object] = {
    "kind": "structural",
    "target_implementation": "cpp_ros2",
    "bytes_per_search_node": 40,
    "bytes_per_tree_node": 40,
    "bytes_per_costmap_cell": 1,
    "costmap_layers": 3,
    "fixed_overhead_mb": 8.0,
}

TUNING: dict[str, object] = {
    "tuning_trials_used": 30,
    "tuning_wall_clock_h": 24.0,
    "n_tunable_params": 12,
    "evidence_log": "artifacts/tuning/optuna.log",
}

MODULAR: dict[str, object] = {
    "type": "modular",
    "global_planner": {"name": "astar", "version": "v1"},
    "local_controller": {"name": "dwa", "version": "v1"},
    "params": {"astar": {"heuristic": "euclidean"}, "dwa": {"sim_time": 1.5}},
    "observation_requirements": ["lidar_2d"],
    "resource_profile": dict(STRUCTURAL),
    "tuning": dict(TUNING),
}

SETTINGS = DecisionSettings()


def candidate(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


A = candidate()
B = candidate(params={"astar": {"heuristic": "manhattan"}, "dwa": {"sim_time": 1.5}})


def anchors():  # type: ignore[no-untyped-def]
    return load_anchors().resolve(make_profile())


def context(seed: int) -> EpisodeContext:
    return EpisodeContext.model_validate(
        {"task_profile_id": "warehouse_a_v1", "mission_id": "m1", "seed": seed}
    )


def episode(owner: Candidate, ctx: EpisodeContext, **overrides: object) -> EpisodeMetricSet:
    payload: dict[str, object] = {
        "episode_context_id": ctx.episode_context_id,
        "candidate_id": owner.candidate_id,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.45,
        "near_miss_rate": 0.05,
        "path_length_m": 44.0,
        "travel_time_s": 60.0,
        "l_ref_m": 40.0,
        "path_efficiency": 0.90,
        "t_ideal_s": 50.0,
        "time_efficiency": 0.80,
        "smoothness": 1.2,
        "stop_and_go_count": 2,
        "p99_latency_ms": 25.0,
        "peak_search_nodes": 412_000,
        "peak_tree_nodes": 0,
        "costmap_cells": 400_000,
        "memory_estimate_mb": 19.0,
        "peak_rss_mb": 340.0,
        "cpu_time_per_mission_s": 2.0,
    }
    payload.update(overrides)
    return EpisodeMetricSet.model_validate(payload)


def scored(
    owner: Candidate,
    *,
    n: int = 9,
    per_episode: dict[int, dict[str, object]] | None = None,
    common: dict[str, object] | None = None,
    seeds: range | None = None,
) -> tuple[CandidateEvidence, dict[str, EpisodeMetricSet]]:
    per_episode = per_episode or {}
    contexts = [context(seed) for seed in (seeds or range(n))]
    metrics = [
        episode(owner, ctx, **{**(common or {}), **per_episode.get(index, {})})
        for index, ctx in enumerate(contexts)
    ]
    return build_evidence(owner, metrics, contexts, anchors(), SETTINGS), index_metrics(metrics)


def ids(n: int = 9) -> list[str]:
    return [context(seed).episode_context_id for seed in range(n)]


# --------------------------------------------------------------------------
# The four roles
# --------------------------------------------------------------------------


def test_the_set_is_always_the_same_four_roles_in_order() -> None:
    winner, metrics_a = scored(A, common={"time_efficiency": 0.90})
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    assert tuple(item.role for item in chosen.exemplars) == EXEMPLAR_ROLES
    assert chosen.n_episodes == 9


def test_both_extremes_travel_together() -> None:
    """Showing the winner's best episode without the runner-up's is the
    cherry-pick the recipe exists to prevent."""
    swing = {0: {"time_efficiency": 1.0}, 8: {"time_efficiency": 0.30}}
    winner, metrics_a = scored(A, per_episode=swing)
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)
    episode_ids = ids()

    assert chosen.by_role("strongest_for_winner").episode_context_id == episode_ids[0]
    assert chosen.by_role("strongest_for_runnerup").episode_context_id == episode_ids[8]
    assert chosen.by_role("strongest_for_winner").delta_utility > 0
    assert chosen.by_role("strongest_for_runnerup").delta_utility < 0


def test_typical_is_the_median_episode_not_the_flattering_one() -> None:
    swing = {index: {"time_efficiency": 0.30 + 0.08 * index} for index in range(9)}
    winner, metrics_a = scored(A, per_episode=swing)
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    typical = chosen.by_role("typical")
    deltas = sorted(
        winner.episode_utilities[key] - loser.episode_utilities[key] for key in winner.contexts
    )
    assert typical.delta_utility == pytest.approx(deltas[4])  # the median of nine


def test_a_collision_invisible_to_delta_u_is_still_the_episode_to_watch() -> None:
    """The role the ΔU ranking gets wrong on its own.

    Both stacks crash in episode 3, so the pair loses the same utility
    and ΔU there is unremarkable — it is neither extreme. No ΔU-based
    rule would ever surface the one episode where a robot hit something.
    """
    crash = {3: {"collision_count": 1, "success": False, "failure_reason": "collision"}}
    swing = {index: {"time_efficiency": 0.30 + 0.08 * index} for index in range(9)}
    winner, metrics_a = scored(A, per_episode={**swing, 3: {**swing[3], **crash[3]}})
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70}, per_episode=crash)

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    safety = chosen.by_role("safety_critical")
    assert safety.episode_context_id == ids()[3]
    assert safety.episode_context_id != chosen.by_role("strongest_for_winner").episode_context_id
    assert safety.episode_context_id != chosen.by_role("strongest_for_runnerup").episode_context_id


def test_a_collision_outranks_any_amount_of_clearance() -> None:
    """A near miss at two centimetres is still not a crash."""
    winner, metrics_a = scored(A, per_episode={5: {"min_clearance": 0.02}})
    loser, metrics_b = scored(
        B,
        common={"time_efficiency": 0.70},
        per_episode={7: {"collision_count": 1, "success": False, "failure_reason": "collision"}},
    )

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    assert chosen.by_role("safety_critical").episode_context_id == ids()[7]


def test_the_worst_clearance_is_read_across_the_pair() -> None:
    """Whichever side had the problem, the episode is worth watching."""
    winner, metrics_a = scored(A, per_episode={2: {"min_clearance": 0.03}})
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    safety = chosen.by_role("safety_critical")
    assert safety.episode_context_id == ids()[2]
    assert safety.criterion == pytest.approx(0.03)


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_ties_go_to_the_episode_id_and_say_that_they_did() -> None:
    """Every episode identical: the recipe must not depend on load order.

    The tie is reported as well as resolved — "worst by a wide margin"
    and "worst by a coin flip the recipe made for you" are different
    pieces of evidence.
    """
    winner, metrics_a = scored(A, common={"time_efficiency": 0.90})
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    smallest = min(ids())
    for role in EXEMPLAR_ROLES:
        item = chosen.by_role(role)
        assert item.episode_context_id == smallest
        assert len(item.tie_break_over) == 8


def test_a_clear_winner_reports_no_tie_break() -> None:
    winner, metrics_a = scored(A, per_episode={0: {"time_efficiency": 1.0}})
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})

    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    assert chosen.by_role("strongest_for_winner").tie_break_over == ()


def test_the_same_evidence_gives_the_same_set() -> None:
    winner, metrics_a = scored(A, per_episode={0: {"time_efficiency": 1.0}})
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})

    first = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)
    second = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)
    assert first.model_dump() == second.model_dump()


# --------------------------------------------------------------------------
# What it refuses
# --------------------------------------------------------------------------


def test_unpaired_episodes_are_refused_before_any_role_is_filled() -> None:
    winner, metrics_a = scored(A, seeds=range(0, 9))
    loser, metrics_b = scored(B, seeds=range(1, 10))

    with pytest.raises(PairingViolation):
        select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)


def test_a_candidate_cannot_be_its_own_runner_up() -> None:
    only, metrics = scored(A)
    with pytest.raises(ExemplarRefusal):
        select_exemplars(only, only, metrics_a=metrics, metrics_b=metrics)


def test_an_episode_with_no_metrics_is_refused_rather_than_skipped() -> None:
    winner, metrics_a = scored(A)
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})
    metrics_b.pop(ids()[4])

    with pytest.raises(ExemplarRefusal, match="no metrics"):
        select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)


def test_one_episode_scored_twice_is_refused() -> None:
    ctx = context(0)
    with pytest.raises(ExemplarRefusal, match="twice"):
        index_metrics([episode(A, ctx), episode(A, ctx, min_clearance=0.1)])


def test_a_set_missing_a_role_cannot_be_constructed() -> None:
    winner, metrics_a = scored(A, common={"time_efficiency": 0.90})
    loser, metrics_b = scored(B, common={"time_efficiency": 0.70})
    chosen = select_exemplars(winner, loser, metrics_a=metrics_a, metrics_b=metrics_b)

    payload = chosen.model_dump()
    payload["exemplars"] = payload["exemplars"][:3]

    with pytest.raises(Exception, match="exactly"):
        ExemplarSet.model_validate(payload)


# --------------------------------------------------------------------------
# From a stored report, months later
# --------------------------------------------------------------------------


def report_row(context: str, utility: float | None, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "episode_context_id": context,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.45,
        "travel_time_s": 60.0,
        "p99_latency_ms": 25.0,
        "replan_count": 0,
        "episode_decision_utility": utility,
    }
    row.update(overrides)
    return row


def stored_report(
    *,
    utilities_a: list[float | None],
    utilities_b: list[float | None],
    card: dict[str, object] | None = None,
    **kw: object,
):
    episodes = [f"ep{index:02d}" for index in range(len(utilities_a))]
    return {
        # The scoring run records the pair the statistics used. Not the
        # card: `alternative` there is a Pareto claim, null on an
        # ordinary run — see the tests at the end of this file.
        "comparison_pair": card
        if card is not None
        else {
            "recommended_candidate_id": "cand_a",
            "runner_up_candidate_id": "cand_b",
        },
        "decision_card": {
            "recommended": {"candidate_id": "cand_a"},
            "alternative": None,
        },
        "candidates": [
            {
                "candidate_id": "cand_a",
                "episodes": [
                    report_row(context, value, **(kw.get("rows_a", {}).get(index, {})))  # type: ignore[union-attr]
                    for index, (context, value) in enumerate(
                        zip(episodes, utilities_a, strict=True)
                    )
                ],
            },
            {
                "candidate_id": "cand_b",
                "episodes": [
                    report_row(context, value, **(kw.get("rows_b", {}).get(index, {})))  # type: ignore[union-attr]
                    for index, (context, value) in enumerate(
                        zip(episodes, utilities_b, strict=True)
                    )
                ],
            },
        ],
    }


def test_the_recipe_runs_off_a_report_read_back_from_the_database() -> None:
    report = stored_report(
        utilities_a=[0.50, 0.90, 0.60, 0.55, 0.30],
        utilities_b=[0.50, 0.50, 0.50, 0.50, 0.50],
    )

    chosen = select_exemplars_from_report(report)

    assert chosen.by_role("strongest_for_winner").episode_context_id == "ep01"
    assert chosen.by_role("strongest_for_runnerup").episode_context_id == "ep04"
    # ΔU is [0, .40, .10, .05, −.20]; the median is .05, which is ep03
    # exactly — not ep00, whose ΔU of 0 is .05 away from it.
    assert chosen.by_role("typical").episode_context_id == "ep03"


def test_the_safety_role_still_reads_across_both_sides_of_a_report() -> None:
    report = stored_report(
        utilities_a=[0.50, 0.60, 0.70],
        utilities_b=[0.50, 0.50, 0.50],
        rows_b={2: {"collision_count": 1, "success": False, "failure_reason": "collision"}},
    )

    assert (
        select_exemplars_from_report(report).by_role("safety_critical").episode_context_id == "ep02"
    )


def test_a_run_scored_before_the_column_existed_gets_no_exemplars() -> None:
    """Refused, not approximated.

    Three of the four roles are defined on ΔU and no column left in the
    report can stand in for it. Substituting travel time would put a
    differently-chosen pair of episodes under a label claiming the
    recipe chose them.
    """
    report = stored_report(utilities_a=[None, None, None], utilities_b=[None, None, None])

    with pytest.raises(ReportExemplarRefusal, match="scored again"):
        select_exemplars_from_report(report, candidate_a="cand_a", candidate_b="cand_b")

    with pytest.raises(ReportExemplarRefusal, match="scored again"):
        select_exemplars_from_report(report)


def test_a_candidate_outside_the_run_is_refused() -> None:
    report = stored_report(utilities_a=[0.6, 0.7], utilities_b=[0.5, 0.5])
    with pytest.raises(ReportExemplarRefusal, match="not in this run"):
        select_exemplars_from_report(report, candidate_a="cand_a", candidate_b="ghost")


def test_the_pair_comes_from_the_card_not_from_report_order() -> None:
    """List order and ranking disagree — the label must follow the card.

    ``cand_b`` is registered first and both carry utility, so "the first
    two scored candidates" would compare them the wrong way round and
    print the runner-up's best episode under ``strongest_for_winner``.
    """
    report = stored_report(
        utilities_a=[0.55, 0.90, 0.40],
        utilities_b=[0.50, 0.50, 0.50],
        card={
            "recommended_candidate_id": "cand_a",
            "runner_up_candidate_id": "cand_b",
        },
    )
    report["candidates"] = list(reversed(report["candidates"]))  # type: ignore[index]

    chosen = select_exemplars_from_report(report)

    assert chosen.candidate_a == "cand_a"
    assert chosen.by_role("strongest_for_winner").episode_context_id == "ep01"
    assert chosen.by_role("strongest_for_runnerup").episode_context_id == "ep02"


def test_a_run_that_ranked_nobody_has_no_winner_to_define_the_roles() -> None:
    report = stored_report(utilities_a=[0.6, 0.7], utilities_b=[0.5, 0.5])
    report["comparison_pair"] = None

    with pytest.raises(ReportExemplarRefusal, match="no comparison pair"):
        select_exemplars_from_report(report)


def test_the_cards_alternative_is_not_the_runner_up_and_is_never_read() -> None:
    """HĐ-12 keeps two different claims apart, and so must this.

    ``alternative`` may only name a PARETO_FRONTIER candidate: it is
    null on every run without that analysis, and when it is set it can
    be a candidate ΔU was never computed against. A version of this
    module read it anyway — which returned nothing for ordinary ranked
    runs and, where it did answer, could name the wrong candidate.
    """
    report = stored_report(utilities_a=[0.55, 0.90, 0.40], utilities_b=[0.5, 0.5, 0.5])
    report["decision_card"] = {
        "recommended": {"candidate_id": "cand_a"},
        "alternative": {"candidate_id": "somebody_else"},
    }

    chosen = select_exemplars_from_report(report)

    assert (chosen.candidate_a, chosen.candidate_b) == ("cand_a", "cand_b")

    # And with the pair missing, the Pareto alternative does not stand in
    # for it.
    report["comparison_pair"] = None
    with pytest.raises(ReportExemplarRefusal, match="no comparison pair"):
        select_exemplars_from_report(report)
