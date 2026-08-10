"""Paired bootstrap ΔU, labels and tie-break (CONTRACTS HĐ-11).

The interesting failures here are not arithmetic. They are the ways a
comparison can produce a confident-looking number about the wrong thing:
unpaired contexts, a tie called by overlapping intervals, a bootstrap
that gives a different answer on the second run, or a tie-break invented
after seeing who it favours.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from task_profile_fakes import make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import DecisionSettings
from planbench_decision.pairing import PairingViolation
from planbench_decision.stats import (
    BOOTSTRAP_RESAMPLES,
    TIE_BREAK_ORDER,
    CandidateEvidence,
    StatisticsRefusal,
    build_evidence,
    compare_pair,
    recommend,
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

ARTIFACT: dict[str, object] = {
    "kind": "artifact",
    "model_artifact_mb": 340.0,
    "runtime_footprint_mb": 900.0,
    "source": "declared",
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

MONOLITHIC: dict[str, object] = {
    "type": "monolithic",
    "policy": {"name": "ppo_navigation", "checkpoint": "ckpt_12", "version": "v1"},
    "observation_requirements": ["lidar_2d"],
    "resource_profile": dict(ARTIFACT),
    "tuning": dict(TUNING),
}


#: Swings ``time_efficiency`` between the anchor's two ends, episode by
#: episode. The mean lands on 0.675 — the midpoint — so a candidate
#: scored on the *set* looks identical to one that sat at 0.675 all
#: along, while the per-episode differences are large enough that the
#: bootstrap cannot resolve a small constant advantage underneath them.
#: That is what a genuine ``NEAR_EQUIVALENT`` looks like.
ALTERNATING_TIME_EFFICIENCY: dict[int, dict[str, object]] = {
    i: {"time_efficiency": 1.0 if i % 2 else 0.35} for i in range(30)
}


def modular(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


def monolithic(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MONOLITHIC, **overrides})


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


def evidence(
    owner: Candidate,
    n: int = 30,
    *,
    per_episode: dict[int, dict[str, object]] | None = None,
    common: dict[str, object] | None = None,
    settings: DecisionSettings | None = None,
) -> CandidateEvidence:
    per_episode = per_episode or {}
    contexts = [context(seed) for seed in range(n)]
    metrics = [
        episode(owner, ctx, **{**(common or {}), **per_episode.get(i, {})})
        for i, ctx in enumerate(contexts)
    ]
    return build_evidence(owner, metrics, contexts, anchors(), settings)


class TestBuildEvidence:
    def test_it_carries_both_aggregation_levels(self) -> None:
        """HĐ-9.1: the set level ranks and prints, the episode level is
        what gets resampled. Neither substitutes for the other."""
        item = evidence(modular(), n=5)
        assert item.set_objectives.level == "set"
        assert len(item.episode_utilities) == 5
        assert all(0.0 <= value <= 1.0 for value in item.episode_utilities.values())

    def test_a_repeated_context_is_refused(self) -> None:
        owner = modular()
        ctx = context(0)
        with pytest.raises(StatisticsRefusal, match="appears twice"):
            build_evidence(owner, [episode(owner, ctx), episode(owner, ctx)], [ctx], anchors())

    def test_an_episode_without_a_context_is_refused(self) -> None:
        owner = modular()
        with pytest.raises(StatisticsRefusal, match="no matching context"):
            build_evidence(owner, [episode(owner, context(0))], [context(1)], anchors())

    def test_episode_level_objectives_are_rejected_as_set_level(self) -> None:
        owner = modular()
        item = evidence(owner, n=3)
        with pytest.raises(ValidationError, match="set-level"):
            CandidateEvidence(
                candidate=owner,
                set_objectives=item.set_objectives.model_copy(update={"level": "episode"}),
                episode_utilities=item.episode_utilities,
            )

    def test_objectives_of_another_candidate_are_refused(self) -> None:
        mine = modular()
        theirs = modular(params={"astar": {"heuristic": "manhattan"}})
        mine_evidence = evidence(mine, n=3)
        theirs_evidence = evidence(theirs, n=3)
        with pytest.raises(ValidationError, match="belong to"):
            CandidateEvidence(
                candidate=mine,
                set_objectives=theirs_evidence.set_objectives,
                episode_utilities=mine_evidence.episode_utilities,
            )


class TestPairing:
    def test_unshared_contexts_are_refused_before_any_number(self) -> None:
        """HĐ-3.2/§17 ban 2. A ΔU over mismatched contexts measures the
        conditions the candidates did not share."""
        a = evidence(modular(), n=30)
        b = evidence(modular(params={"astar": {"heuristic": "manhattan"}}), n=29)
        with pytest.raises(PairingViolation, match="did not run the same"):
            compare_pair(a, b)

    def test_a_candidate_cannot_be_compared_with_itself(self) -> None:
        item = evidence(modular(), n=5)
        with pytest.raises(StatisticsRefusal, match="itself"):
            compare_pair(item, item)


class TestBootstrap:
    def test_a_consistent_advantage_excludes_zero(self) -> None:
        """Better in every episode, by a margin the noise cannot cover."""
        better = modular()
        worse = modular(params={"astar": {"heuristic": "manhattan"}})
        a = evidence(better, common={"p99_latency_ms": 12.0})
        b = evidence(worse, common={"p99_latency_ms": 45.0})

        result = compare_pair(a, b)
        assert result.delta_mean > 0
        assert result.excludes_zero
        assert result.status == "CLEAR_RECOMMENDATION"
        assert result.ci95[0] > 0

    def test_identical_candidates_straddle_zero(self) -> None:
        """Same metrics episode by episode: ΔU is exactly 0 everywhere,
        so the interval sits on zero and the label must not claim more."""
        a = evidence(modular())
        b = evidence(modular(params={"astar": {"heuristic": "manhattan"}}))
        result = compare_pair(a, b)
        assert result.delta_mean == pytest.approx(0.0)
        assert result.ci95 == (0.0, 0.0)
        assert not result.excludes_zero
        assert result.status == "NEAR_EQUIVALENT"

    def test_noise_without_a_real_gap_stays_near_equivalent(self) -> None:
        """A tiny edge that flips sign across episodes is not evidence.

        The rule has the property HĐ-10.2 demands of every elimination
        rule: with weak data it concludes nothing.
        """
        a_metrics = {i: {"p99_latency_ms": 25.0 + (3.0 if i % 2 else -3.0)} for i in range(30)}
        b_metrics = {i: {"p99_latency_ms": 25.0 - (3.0 if i % 2 else -3.0)} for i in range(30)}
        a = evidence(modular(), per_episode=a_metrics)
        b = evidence(modular(params={"astar": {"heuristic": "manhattan"}}), per_episode=b_metrics)
        assert not compare_pair(a, b).excludes_zero

    def test_the_same_seed_gives_the_same_interval(self) -> None:
        """HĐ-15.1 criterion 2: rebuilt from a manifest, the card has to
        come back identical to six decimals. A bootstrap seeded from the
        clock cannot do that."""
        a = evidence(modular(), per_episode={i: {"p99_latency_ms": 20.0 + i} for i in range(30)})
        b = evidence(
            modular(params={"astar": {"heuristic": "manhattan"}}),
            per_episode={i: {"p99_latency_ms": 22.0 + i} for i in range(30)},
        )
        first = compare_pair(a, b, seed=7)
        second = compare_pair(a, b, seed=7)
        third = compare_pair(a, b, seed=8)
        assert first.ci95 == second.ci95
        assert first.ci95 != third.ci95

    def test_it_records_how_it_was_computed(self) -> None:
        result = compare_pair(
            evidence(modular(), n=10),
            evidence(modular(params={"astar": {"heuristic": "manhattan"}}), n=10),
            seed=3,
        )
        assert (result.seed, result.n_resamples) == (3, BOOTSTRAP_RESAMPLES)
        assert result.n_episodes == 10

    def test_zero_variance_reports_no_effect_size(self) -> None:
        """Every episode gave the same difference. The standardised
        effect divides by zero spread; ``inf`` would put a number where
        the data has none."""
        a = evidence(modular(), common={"p99_latency_ms": 12.0})
        b = evidence(
            modular(params={"astar": {"heuristic": "manhattan"}}), common={"p99_latency_ms": 45.0}
        )
        assert compare_pair(a, b).effect_size is None

    def test_effect_size_is_reported_when_it_is_defined(self) -> None:
        a = evidence(
            modular(), per_episode={i: {"p99_latency_ms": 12.0 + i * 0.5} for i in range(30)}
        )
        b = evidence(
            modular(params={"astar": {"heuristic": "manhattan"}}),
            per_episode={i: {"p99_latency_ms": 40.0 + i * 0.1} for i in range(30)},
        )
        result = compare_pair(a, b)
        assert result.effect_size is not None
        assert result.effect_size > 0

    def test_no_p_value_is_reported(self) -> None:
        """HĐ-11.3 forbids a bare p-value; this module computes none."""
        result = compare_pair(
            evidence(modular(), n=5),
            evidence(modular(params={"astar": {"heuristic": "manhattan"}}), n=5),
        )
        assert not [name for name in result.model_dump() if "p_value" in name]

    def test_the_required_report_fields_are_all_present(self) -> None:
        """HĐ-11.3 minimum: median, IQR, CI95, effect size, n."""
        fields = compare_pair(
            evidence(modular(), n=5),
            evidence(modular(params={"astar": {"heuristic": "manhattan"}}), n=5),
        ).model_dump()
        assert {"delta_median", "delta_iqr", "ci95", "effect_size", "n_episodes"} <= set(fields)


class TestRecommendation:
    def test_one_candidate_is_refused(self) -> None:
        with pytest.raises(StatisticsRefusal, match="at least two"):
            recommend([evidence(modular(), n=5)])

    def test_the_same_candidate_twice_is_refused(self) -> None:
        item = evidence(modular(), n=5)
        with pytest.raises(StatisticsRefusal, match="more than once"):
            recommend([item, item])

    def test_a_clear_winner_is_named_without_a_tie_break(self) -> None:
        better = modular()
        worse = modular(params={"astar": {"heuristic": "manhattan"}})
        result = recommend(
            [
                evidence(worse, common={"p99_latency_ms": 45.0}),
                evidence(better, common={"p99_latency_ms": 12.0}),
            ]
        )
        assert result.status == "CLEAR_RECOMMENDATION"
        assert result.recommended_id == better.candidate_id
        assert result.runner_up_id == worse.candidate_id
        assert result.tie_break_reason is None
        assert result.ranking[0] == better.candidate_id

    def test_a_tie_still_produces_exactly_one_recommendation(self) -> None:
        """HĐ-11.3: NEAR_EQUIVALENT does not mean "pick either"."""
        result = recommend(
            [
                evidence(modular()),
                evidence(modular(params={"astar": {"heuristic": "manhattan"}})),
            ]
        )
        assert result.status == "NEAR_EQUIVALENT"
        assert result.recommended_id
        assert result.tie_break_reason is not None

    def test_only_the_top_two_are_compared(self) -> None:
        best = modular()
        middle = modular(params={"astar": {"heuristic": "manhattan"}})
        worst = modular(params={"astar": {"heuristic": "chebyshev"}})
        result = recommend(
            [
                evidence(worst, common={"p99_latency_ms": 48.0}),
                evidence(best, common={"p99_latency_ms": 11.0}),
                evidence(middle, common={"p99_latency_ms": 30.0}),
            ]
        )
        assert result.ranking == (best.candidate_id, middle.candidate_id, worst.candidate_id)
        assert {result.comparison.candidate_a, result.comparison.candidate_b} == {
            best.candidate_id,
            middle.candidate_id,
        }

    def test_the_label_comes_from_the_paired_ci_not_from_overlap(self) -> None:
        """§17 ban 5. Both candidates swing widely across episodes — their
        individual intervals overlap heavily — yet one is better in every
        single episode by a steady margin, and the paired CI says so.
        """
        swing = {i: {"p99_latency_ms": 15.0 + (i % 10) * 3.0} for i in range(30)}
        a = evidence(modular(), per_episode=swing)
        b = evidence(
            modular(params={"astar": {"heuristic": "manhattan"}}),
            per_episode={i: {"p99_latency_ms": 18.0 + (i % 10) * 3.0} for i in range(30)},
        )
        assert compare_pair(a, b).excludes_zero


class TestTieBreak:
    """HĐ-11.3's ladder, declared in advance and applied in order."""

    def test_the_declared_order_is_the_contracts(self) -> None:
        assert len(TIE_BREAK_ORDER) == 4
        assert TIE_BREAK_ORDER[0].startswith("U_C")
        assert "modular" in TIE_BREAK_ORDER[3]

    def test_rung_one_is_cheaper_wins(self) -> None:
        """A small cost edge, drowned in per-episode noise.

        The cheaper candidate declared 20 tuning hours against 24, worth
        about 0.01 of utility — real, constant, and far smaller than the
        ±0.06 the two swap back and forth on efficiency episode by
        episode. The CI therefore contains zero, and U_C is the first
        rung that separates them.

        Note what makes this a tie rather than a win: a cost advantage on
        its own is a *constant* shift, so with everything else equal the
        CI would exclude zero and the label would be
        ``CLEAR_RECOMMENDATION``. It takes genuine episode-to-episode
        variation to make the difference unresolvable.
        """
        cheap = modular(tuning={**TUNING, "tuning_wall_clock_h": 20.0})
        pricey = modular(
            params={"astar": {"heuristic": "manhattan"}},
            tuning={**TUNING, "tuning_wall_clock_h": 24.0},
        )
        result = recommend(
            [
                evidence(pricey, common={"time_efficiency": 0.675}),
                evidence(cheap, per_episode=ALTERNATING_TIME_EFFICIENCY),
            ]
        )
        assert result.status == "NEAR_EQUIVALENT"
        assert result.recommended_id == cheap.candidate_id
        assert result.tie_break_reason == TIE_BREAK_ORDER[0]

    def test_rung_two_prefers_the_steadier_candidate(self) -> None:
        """Same U_C, same mean utility, different spread across episodes.

        A candidate that does the same thing every time is the better bet
        at equal average, which is what this rung says out loud.
        """
        steady = modular()
        erratic = modular(params={"astar": {"heuristic": "manhattan"}})
        steady_metrics = {i: {"path_efficiency": 0.90} for i in range(30)}
        erratic_metrics = {i: {"path_efficiency": 0.80 if i % 2 else 1.00} for i in range(30)}
        result = recommend(
            [
                evidence(erratic, per_episode=erratic_metrics),
                evidence(steady, per_episode=steady_metrics),
            ]
        )
        assert result.status == "NEAR_EQUIVALENT"
        assert result.recommended_id == steady.candidate_id
        assert result.tie_break_reason == TIE_BREAK_ORDER[1]

    def test_rung_three_prefers_fewer_knobs(self) -> None:
        simple = modular(tuning={**TUNING, "n_tunable_params": 3})
        fiddly = modular(
            params={"astar": {"heuristic": "manhattan"}},
            tuning={**TUNING, "n_tunable_params": 25},
        )
        result = recommend([evidence(fiddly), evidence(simple)])
        assert result.recommended_id == simple.candidate_id
        assert result.tie_break_reason == TIE_BREAK_ORDER[2]

    def test_an_undeclared_parameter_count_loses_that_rung(self) -> None:
        """The rung rewards "fewer knobs to maintain". A candidate that
        never said how many it has has not earned that credit — but it is
        only scoreable at all under a profile that ignores tuning cost."""
        declared = modular(tuning={**TUNING, "n_tunable_params": 25})
        silent = modular(params={"astar": {"heuristic": "manhattan"}}, tuning=None)
        settings = DecisionSettings(preference_profile="measured_only")
        result = recommend(
            [evidence(silent, settings=settings), evidence(declared, settings=settings)]
        )
        assert result.recommended_id == declared.candidate_id
        assert result.tie_break_reason == TIE_BREAK_ORDER[2]

    def test_rung_four_prefers_modular(self) -> None:
        """Last rung: a stack whose layers can be inspected and swapped
        beats a policy that can only be replaced wholesale."""
        stack = modular()
        policy = monolithic()
        result = recommend([evidence(policy), evidence(stack)])
        assert result.status == "NEAR_EQUIVALENT"
        assert result.recommended_id == stack.candidate_id
        assert result.tie_break_reason == TIE_BREAK_ORDER[3]

    def test_a_total_tie_keeps_the_ranking(self) -> None:
        """Indistinguishable on all four declared axes. Keeping the raw
        ranking is what makes the outcome reproducible rather than
        arbitrary — and the reason is stated, not hidden."""
        a = modular()
        b = modular(params={"astar": {"heuristic": "manhattan"}})
        result = recommend([evidence(a), evidence(b)])
        assert result.status == "NEAR_EQUIVALENT"
        assert result.tie_break_reason == (
            "hòa trên cả bốn tiêu chí phụ; giữ thứ hạng theo decision_utility"
        )
        assert result.recommended_id == result.ranking[0]

    def test_a_tie_break_can_overturn_the_raw_ranking(self) -> None:
        """The point of the ladder. The candidate with the marginally
        higher decision_utility does not automatically win once the
        difference is inside the noise."""
        pricey = modular(tuning={**TUNING, "tuning_wall_clock_h": 24.0})
        cheap = modular(
            params={"astar": {"heuristic": "manhattan"}},
            tuning={**TUNING, "tuning_wall_clock_h": 20.0},
        )
        # The pricier candidate takes the top of the ranking on a small
        # path-efficiency edge, worth more than the cheaper one's cost
        # advantage but far less than the noise the two swap on time.
        leader = evidence(pricey, common={"time_efficiency": 0.675, "path_efficiency": 0.96})
        result = recommend([leader, evidence(cheap, per_episode=ALTERNATING_TIME_EFFICIENCY)])

        assert result.ranking[0] == pricey.candidate_id
        assert result.status == "NEAR_EQUIVALENT"
        assert result.recommended_id == cheap.candidate_id
        assert result.tie_break_reason == TIE_BREAK_ORDER[0]
