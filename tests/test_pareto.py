"""Pareto labelling by non-inferiority (CONTRACTS HĐ-10).

The topic document records getting this rule wrong twice, in opposite
directions, so most of these tests are about the two wrong versions
rather than the right one: a rule too strict to ever fire, and a rule
that concludes *more* the *less* data it has.

The contract's own acceptance test heads the file — *if there were no
data, what would the rule do?* — because every elimination rule in this
project has to answer "nothing".
"""

from __future__ import annotations

import pytest
from task_profile_fakes import make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import DecisionSettings
from planbench_decision.pareto import (
    DEFAULT_EPSILON,
    ParetoError,
    choose_alternative,
    compare_objectives,
    dominance,
    label_field,
)
from planbench_decision.stats import CandidateEvidence, build_evidence
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

HEURISTICS = ("euclidean", "manhattan", "octile", "chebyshev")


def candidate(index: int = 0) -> Candidate:
    """Distinct candidates that differ only in a parameter nobody scores."""
    return Candidate.model_validate(
        {
            **MODULAR,
            "params": {"astar": {"heuristic": HEURISTICS[index]}, "dwa": {"sim_time": 1.5}},
        }
    )


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
        "min_clearance": 0.13,
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
    owner: Candidate, traits: dict[str, object], *, n: int = 30, jitter: float = 0.002
) -> CandidateEvidence:
    """One candidate scored over ``n`` episodes with a little spread.

    Without spread every bootstrap resample gives the identical mean, the
    CI collapses to a point, and the tolerance ε is the only thing left
    doing any work — which would test ε rather than the rule.
    """
    contexts = [context(seed) for seed in range(n)]
    metrics = [
        episode(
            owner,
            ctx,
            **{**traits, "path_efficiency": 0.90 + (index % 5) * jitter},
        )
        for index, ctx in enumerate(contexts)
    ]
    return build_evidence(owner, metrics, contexts, anchors(), DecisionSettings())


#: Better on cost, worse on safety. Neither dominates the other, which
#: is the interesting case: both belong on the frontier.
FAST = {"p99_latency_ms": 8.0, "min_clearance": 0.05}
SAFE = {"p99_latency_ms": 45.0, "min_clearance": 0.26}

#: Worse than FAST on every objective at once.
WORSE_EVERYWHERE = {
    "p99_latency_ms": 48.0,
    "min_clearance": 0.02,
    "near_miss_rate": 0.30,
    "time_efficiency": 0.40,
    "path_efficiency": 0.70,
    "cpu_time_per_mission_s": 8.0,
    "memory_estimate_mb": 300.0,
}


class TestTheContractsAcceptanceTest:
    """HĐ-10.2: *if there were no data, what would the rule do?* The
    answer must be "nothing", and it must be "nothing" in the labelling
    too, not merely in the dominance predicate."""

    def test_a_single_episode_concludes_nothing(self) -> None:
        strong = evidence(candidate(0), FAST, n=1)
        weak = evidence(candidate(1), WORSE_EVERYWHERE, n=1)
        assert not dominance(strong, weak)
        assert not dominance(weak, strong)

    def test_and_labels_everyone_uncertain(self) -> None:
        report = label_field(
            [evidence(candidate(0), FAST, n=1), evidence(candidate(1), WORSE_EVERYWHERE, n=1)]
        )
        assert set(report.labels.values()) == {"UNCERTAIN_DOMINANCE"}
        assert report.frontier == ()

    def test_thin_data_never_concludes_more_than_thick_data(self) -> None:
        """The property the rejected rule lacked. Under "CI not entirely
        below 0", fewer episodes widen the interval and make dominance
        *easier* to claim. Here the same pair, genuinely dominated, is
        only concluded once there is enough evidence."""
        strong, weak = candidate(0), candidate(1)
        thin = dominance(evidence(strong, FAST, n=2), evidence(weak, WORSE_EVERYWHERE, n=2))
        thick = dominance(evidence(strong, FAST, n=30), evidence(weak, WORSE_EVERYWHERE, n=30))
        assert thick
        assert not thin


class TestDominance:
    def test_worse_on_everything_is_dominated(self) -> None:
        assert dominance(evidence(candidate(0), FAST), evidence(candidate(1), WORSE_EVERYWHERE))

    def test_dominance_is_not_symmetric(self) -> None:
        strong = evidence(candidate(0), FAST)
        weak = evidence(candidate(1), WORSE_EVERYWHERE)
        assert dominance(strong, weak)
        assert not dominance(weak, strong)

    def test_a_trade_off_is_not_dominance(self) -> None:
        """Better on cost, worse on safety: no non-negative weighting
        rules either one out, so neither may be eliminated."""
        fast, safe = evidence(candidate(0), FAST), evidence(candidate(1), SAFE)
        assert not dominance(fast, safe)
        assert not dominance(safe, fast)

    def test_a_tie_everywhere_is_not_dominance(self) -> None:
        """The rejected "≥ ε on every objective" rule failed the other
        way — but so would a rule that let equality count as winning.
        Dominance needs to be *better* somewhere."""
        left, right = evidence(candidate(0), FAST), evidence(candidate(1), FAST)
        assert not dominance(left, right)
        assert not dominance(right, left)

    def test_one_tied_objective_does_not_switch_the_rule_off(self) -> None:
        """The first wrong version, in one assertion. Requiring a margin
        on *every* objective means a single tie disables the filter even
        when the lead everywhere else is decisive.

        Here both candidates have identical reliability — every episode
        succeeds, so U_R ties exactly — and one is worse on all three of
        the others. It must still be dominated.
        """
        verdict = compare_objectives(
            evidence(candidate(0), FAST), evidence(candidate(1), WORSE_EVERYWHERE)
        )
        tied = [i for i in verdict.intervals if i.objective == "U_R"]
        assert tied and tied[0].delta_mean == pytest.approx(0.0, abs=1e-12)
        assert verdict.dominates

    def test_a_candidate_cannot_dominate_itself(self) -> None:
        item = evidence(candidate(0), FAST)
        with pytest.raises(ParetoError, match="cannot dominate itself"):
            compare_objectives(item, item)

    def test_a_zero_tolerance_is_refused(self) -> None:
        with pytest.raises(ParetoError, match="epsilon must be positive"):
            compare_objectives(
                evidence(candidate(0), FAST), evidence(candidate(1), SAFE), epsilon=0.0
            )

    def test_mismatched_context_sets_are_refused_before_any_number(self) -> None:
        """Same rule as the head-to-head comparison: a ΔU taken across
        different episodes answers a question nobody asked."""
        with pytest.raises(ValueError, match="did not run the same episodes"):
            compare_objectives(
                evidence(candidate(0), FAST, n=30), evidence(candidate(1), SAFE, n=20)
            )

    def test_it_is_reproducible(self) -> None:
        left, right = evidence(candidate(0), FAST), evidence(candidate(1), SAFE)
        assert compare_objectives(left, right, seed=7) == compare_objectives(left, right, seed=7)


class TestLabelling:
    def test_a_trade_off_puts_both_on_the_frontier(self) -> None:
        report = label_field([evidence(candidate(0), FAST), evidence(candidate(1), SAFE)])
        assert set(report.labels.values()) == {"PARETO_FRONTIER"}
        assert len(report.frontier) == 2

    def test_the_dominated_candidate_is_labelled_not_removed(self) -> None:
        """HĐ-10.1: nobody disappears from the report. The row stays; what
        it loses is the right to be offered."""
        strong, weak = candidate(0), candidate(1)
        report = label_field([evidence(strong, FAST), evidence(weak, WORSE_EVERYWHERE)])
        assert report.labels[weak.candidate_id] == "LIKELY_DOMINATED"
        assert weak.candidate_id in report.labels
        assert report.dominated_by(weak.candidate_id) == (strong.candidate_id,)

    def test_the_dominator_keeps_the_frontier(self) -> None:
        strong = candidate(0)
        report = label_field([evidence(strong, FAST), evidence(candidate(1), WORSE_EVERYWHERE)])
        assert report.labels[strong.candidate_id] == "PARETO_FRONTIER"

    def test_a_lone_candidate_is_uncertain_not_frontier(self) -> None:
        """ "Nobody dominates it" is trivially true with no rivals, and
        would read on a card as an established finding."""
        report = label_field([evidence(candidate(0), FAST)])
        assert report.labels == {candidate(0).candidate_id: "UNCERTAIN_DOMINANCE"}

    def test_three_candidates_split_into_all_three_labels(self) -> None:
        fast, safe, poor = candidate(0), candidate(1), candidate(2)
        report = label_field(
            [
                evidence(fast, FAST),
                evidence(safe, SAFE),
                evidence(poor, WORSE_EVERYWHERE),
            ]
        )
        assert report.labels[fast.candidate_id] == "PARETO_FRONTIER"
        assert report.labels[poor.candidate_id] == "LIKELY_DOMINATED"
        # Safe is not dominated by fast (it trades), and dominates poor.
        assert report.labels[safe.candidate_id] in ("PARETO_FRONTIER", "UNCERTAIN_DOMINANCE")

    def test_labelling_an_outsider_is_refused(self) -> None:
        report = label_field([evidence(candidate(0), FAST), evidence(candidate(1), SAFE)])
        with pytest.raises(ParetoError, match="not part of this Pareto analysis"):
            report.label_of("deadbeefcafe")

    def test_every_ordered_pair_is_compared(self) -> None:
        """Dominance is not symmetric, so comparing each unordered pair
        once would have to pick a direction — and the direction would be
        whoever sorted the list."""
        report = label_field([evidence(candidate(0), FAST), evidence(candidate(1), SAFE)])
        assert len(report.verdicts) == 2


class TestAlternative:
    """HĐ-12: ``alternative`` comes only from the frontier."""

    def test_it_offers_the_best_frontier_rival(self) -> None:
        fast, safe = candidate(0), candidate(1)
        report = label_field([evidence(fast, FAST), evidence(safe, SAFE)])
        chosen = choose_alternative(
            report, fast.candidate_id, [fast.candidate_id, safe.candidate_id]
        )
        assert chosen == safe.candidate_id

    def test_a_dominated_runner_up_is_never_offered(self) -> None:
        """The failure this rule exists for: the statistical runner-up
        can be worse on every objective at once, and offering it as a
        near-equivalent alternative invites a reader to switch to it."""
        strong, weak = candidate(0), candidate(1)
        report = label_field([evidence(strong, FAST), evidence(weak, WORSE_EVERYWHERE)])
        assert (
            choose_alternative(
                report, strong.candidate_id, [strong.candidate_id, weak.candidate_id]
            )
            is None
        )

    def test_no_second_frontier_candidate_means_no_alternative(self) -> None:
        report = label_field([evidence(candidate(0), FAST)])
        assert (
            choose_alternative(report, candidate(0).candidate_id, [candidate(0).candidate_id])
            is None
        )

    def test_it_follows_the_ranking_order(self) -> None:
        fast, safe = candidate(0), candidate(1)
        report = label_field([evidence(fast, FAST), evidence(safe, SAFE)])
        # Recommending SAFE: the only frontier rival left is FAST.
        assert (
            choose_alternative(report, safe.candidate_id, [safe.candidate_id, fast.candidate_id])
            == fast.candidate_id
        )


class TestTolerance:
    def test_the_default_is_the_contracts(self) -> None:
        assert DEFAULT_EPSILON == 0.02

    def test_a_wider_tolerance_concludes_less(self) -> None:
        """ε is a practical indifference band, so widening it can only
        make dominance harder to establish, never easier."""
        strong, weak = evidence(candidate(0), FAST), evidence(candidate(1), WORSE_EVERYWHERE)
        assert dominance(strong, weak, epsilon=0.02)
        assert not dominance(strong, weak, epsilon=0.95)
